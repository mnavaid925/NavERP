"""Procurement 6.11 Order Fulfillment & Tracking — view / CRUD integration flows.

Every surface is exercised through the real URLconf and rendered bytes: the three registers
plus the two computed boards (search, each filter, ``?late=1``, junk FK params, page 2 and a
page past the end), the create/edit/delete verbs, the ASN lifecycle POSTs, the split console,
and the backorder reschedule / close / escalate POSTs.

Contract discipline: a context key is only asserted "present" together with an assertion that it
is POPULATED (L41), dates derive from ``timezone.localdate()`` (L16), and the list pages are
wrapped in ``django_assert_max_num_queries`` because every one of them renders a chained
``__str__`` FK hop.
"""
import datetime
from decimal import Decimal

import pytest

from django.contrib.contenttypes.models import ContentType
from django.urls import reverse
from django.utils import timezone

from apps.core.models import AuditLog
from apps.procurement.models import (AdvancedShipmentNotice, AsnLine, Backorder,
                                     DeliverySchedule, ProcurementAlert)

pytestmark = pytest.mark.django_db


# ------------------------------------------------------------------ helpers

def _fulfillment_today():
    """The SAME basis every 6.11 property uses — never ``date.today()`` (L16)."""
    return timezone.localdate()


def _fulfillment_days(n):
    return datetime.timedelta(days=n)


def _fulfillment_templates(response):
    return [t.name for t in response.templates if t.name]


def _fulfillment_messages(response):
    """Flash messages rendered after a followed redirect."""
    return [str(m) for m in response.context["messages"]]


def _fulfillment_pks(response):
    return [o.pk for o in response.context["object_list"]]


def _fulfillment_audit(model, obj, action):
    ct = ContentType.objects.get_for_model(model)
    return AuditLog.objects.filter(content_type=ct, object_id=obj.pk, action=action)


def _fulfillment_bulk_asns(tenant, po, count, *, status="draft", expected=None):
    """``count`` notices on one order — enough to push the 15-row page size over to page 2."""
    rows = []
    for index in range(count):
        rows.append(AdvancedShipmentNotice.objects.create(
            tenant=tenant, purchase_order=po, status=status,
            supplier_reference="BULK-%03d" % index,
            tracking_number="TRKB-%03d" % index,
            carrier_name="Bulk Freight",
            expected_delivery_date=(expected if expected is not None
                                    else _fulfillment_today() + _fulfillment_days(index + 1))))
    return rows


def _fulfillment_bulk_schedules(tenant, po_line, count, *, first_sequence=100):
    rows = []
    for index in range(count):
        rows.append(DeliverySchedule.objects.create(
            tenant=tenant, po_line=po_line, sequence=first_sequence + index,
            scheduled_quantity=Decimal("1"),
            need_by_date=_fulfillment_today() + _fulfillment_days(index + 1),
            status="planned", delivery_mode="standard"))
    return rows


def _fulfillment_bulk_backorders(tenant, po_line, count):
    rows = []
    for index in range(count):
        rows.append(Backorder.objects.create(
            tenant=tenant, po_line=po_line, quantity_backordered=Decimal("1"),
            reason="logistics", status="open",
            revised_promise_date=_fulfillment_today() + _fulfillment_days(index + 1)))
    return rows


def _fulfillment_asn_header_post(**overrides):
    """A complete, valid ASN header POST body (edit shape — no ``purchase_order``)."""
    body = {
        "supplier_reference": "", "source": "manual", "ship_date": "",
        "expected_delivery_date": "", "carrier": "", "carrier_name": "Northwind Express",
        "tracking_number": "", "shipment": "", "bill_of_lading_ref": "", "container_ref": "",
        "freight_terms": "", "package_count": "", "pallet_count": "", "gross_weight_kg": "",
        "volume_cbm": "", "notes": "",
    }
    body.update(overrides)
    return body


def _fulfillment_line_management(total=1, initial=0):
    return {
        "lines-TOTAL_FORMS": str(total), "lines-INITIAL_FORMS": str(initial),
        "lines-MIN_NUM_FORMS": "0", "lines-MAX_NUM_FORMS": "50",
    }


def _fulfillment_schedule_post(**overrides):
    body = {
        "po_line": "", "sequence": "1", "scheduled_quantity": "2",
        "need_by_date": (_fulfillment_today() + _fulfillment_days(9)).strftime("%Y-%m-%d"),
        "promised_quantity": "", "promised_date": "", "status": "planned",
        "ship_to": "", "delivery_mode": "standard", "asn": "", "change_reason": "", "notes": "",
    }
    body.update(overrides)
    return body


def _fulfillment_backorder_post(**overrides):
    body = {
        "po_line": "", "delivery_schedule": "", "asn": "", "quantity_backordered": "3",
        "reason": "out_of_stock", "reason_note": "", "original_promise_date": "",
        "revised_promise_date": "", "notes": "",
    }
    body.update(overrides)
    return body


# ================================================================== ASN register


def test_fulfillment_asn_list_renders_contract_context(client_a, fulfillment_asn_draft_a,
                                                       fulfillment_asn_in_transit_a,
                                                       fulfillment_asn_late_a,
                                                       fulfillment_asn_delivered_a,
                                                       fulfillment_carrier_a):
    r = client_a.get(reverse("procurement:asn_list"))
    assert r.status_code == 200
    assert "procurement/orderfulfillment/asn/list.html" in _fulfillment_templates(r)

    ctx = r.context
    assert len(ctx["object_list"]) == 4
    assert ctx["page_obj"].paginator.count == 4
    assert ctx["q"] == ""
    assert [v for v, _ in ctx["status_choices"]] == ["draft", "submitted", "in_transit",
                                                     "delivered", "cancelled"]
    assert [v for v, _ in ctx["source_choices"]] == ["portal", "email", "edi", "manual"]
    assert [c.pk for c in ctx["carriers"]] == [fulfillment_carrier_a.pk]
    assert [o.pk for o in ctx["purchase_orders"]] == [fulfillment_asn_draft_a.purchase_order_id]
    assert ctx["stats"] == {"total": 4, "in_flight": 2, "late": 1, "delivered": 1}

    body = r.content.decode()
    for asn in (fulfillment_asn_draft_a, fulfillment_asn_late_a, fulfillment_asn_delivered_a):
        assert asn.number in body
    assert "3d late" in body  # the late fixture is three days overdue


@pytest.mark.parametrize("term_attr", ["number", "supplier_reference", "tracking_number"])
def test_fulfillment_asn_list_search_matches_each_field(client_a, fulfillment_asn_late_a,
                                                        fulfillment_asn_draft_a, term_attr):
    term = getattr(fulfillment_asn_late_a, term_attr)
    r = client_a.get(reverse("procurement:asn_list"), {"q": term})
    assert r.status_code == 200
    assert _fulfillment_pks(r) == [fulfillment_asn_late_a.pk]
    assert r.context["q"] == term


def test_fulfillment_asn_list_search_matches_order_number(client_a, fulfillment_asn_draft_a,
                                                          fulfillment_po_a):
    r = client_a.get(reverse("procurement:asn_list"), {"q": fulfillment_po_a.number})
    assert _fulfillment_pks(r) == [fulfillment_asn_draft_a.pk]

    r = client_a.get(reverse("procurement:asn_list"), {"q": "no-such-shipment"})
    assert r.status_code == 200 and _fulfillment_pks(r) == []


def test_fulfillment_asn_list_status_and_source_filters(client_a, fulfillment_asn_draft_a,
                                                        fulfillment_asn_in_transit_a,
                                                        fulfillment_asn_delivered_a):
    url = reverse("procurement:asn_list")
    r = client_a.get(url, {"status": "delivered"})
    assert _fulfillment_pks(r) == [fulfillment_asn_delivered_a.pk]

    r = client_a.get(url, {"status": "in_transit"})
    assert _fulfillment_pks(r) == [fulfillment_asn_in_transit_a.pk]

    r = client_a.get(url, {"source": "manual"})
    assert len(_fulfillment_pks(r)) == 3
    r = client_a.get(url, {"source": "edi"})
    assert _fulfillment_pks(r) == []


def test_fulfillment_asn_list_carrier_and_po_filters(client_a, fulfillment_asn_draft_a,
                                                     fulfillment_asn_in_transit_a,
                                                     fulfillment_carrier_a, fulfillment_po_a):
    url = reverse("procurement:asn_list")
    AdvancedShipmentNotice.objects.filter(pk=fulfillment_asn_draft_a.pk).update(
        carrier=fulfillment_carrier_a)

    r = client_a.get(url, {"carrier": str(fulfillment_carrier_a.pk)})
    assert _fulfillment_pks(r) == [fulfillment_asn_draft_a.pk]

    r = client_a.get(url, {"po": str(fulfillment_po_a.pk)})
    assert set(_fulfillment_pks(r)) == {fulfillment_asn_draft_a.pk,
                                        fulfillment_asn_in_transit_a.pk}

    r = client_a.get(url, {"po": str(fulfillment_po_a.pk + 9999)})
    assert _fulfillment_pks(r) == []


def test_fulfillment_asn_list_late_flag_narrows_before_pagination(client_a,
                                                                  fulfillment_asn_late_a,
                                                                  fulfillment_asn_in_transit_a,
                                                                  fulfillment_asn_delivered_a):
    r = client_a.get(reverse("procurement:asn_list"), {"late": "1"})
    assert r.status_code == 200
    assert _fulfillment_pks(r) == [fulfillment_asn_late_a.pk]
    # the paginator counts the SAME rows the page shows
    assert r.context["page_obj"].paginator.count == 1
    # the stat cards stay whole-workspace, deliberately
    assert r.context["stats"]["total"] == 3


@pytest.mark.parametrize("params", [
    {"carrier": "abc"}, {"carrier": "9999999999999999999999"}, {"po": "abc"},
    {"po": "9999999999999999999999"}, {"status": "zzz"}, {"source": "zzz"},
    {"carrier": "-1"}, {"po": ""},
])
def test_fulfillment_asn_list_junk_params_never_500(client_a, fulfillment_asn_draft_a, params):
    r = client_a.get(reverse("procurement:asn_list"), params)
    assert r.status_code == 200
    assert "object_list" in r.context


def test_fulfillment_asn_list_pagination_page_two_and_past_the_end(client_a, tenant_a,
                                                                   fulfillment_po_a):
    _fulfillment_bulk_asns(tenant_a, fulfillment_po_a, 18)
    url = reverse("procurement:asn_list")

    first = client_a.get(url)
    assert len(first.context["object_list"]) == 15
    assert first.context["page_obj"].number == 1
    assert first.context["page_obj"].paginator.num_pages == 2

    second = client_a.get(url, {"page": "2"})
    assert second.status_code == 200
    assert len(second.context["object_list"]) == 3
    assert second.context["page_obj"].number == 2
    assert set(_fulfillment_pks(first)).isdisjoint(_fulfillment_pks(second))

    past = client_a.get(url, {"page": "999"})
    assert past.status_code == 200 and past.context["page_obj"].number == 2

    junk = client_a.get(url, {"page": "abc"})
    assert junk.status_code == 200 and junk.context["page_obj"].number == 1


def test_fulfillment_asn_list_query_count_is_bounded(client_a, tenant_a, fulfillment_po_a,
                                                     fulfillment_carrier_a,
                                                     django_assert_max_num_queries):
    # 15 rows, each rendering purchase_order.number, purchase_order.vendor.name and
    # carrier_display -> carrier.party.name. Without the select_related chain this is 60+.
    rows = _fulfillment_bulk_asns(tenant_a, fulfillment_po_a, 15)
    AdvancedShipmentNotice.objects.filter(pk__in=[r.pk for r in rows]).update(
        carrier=fulfillment_carrier_a)
    with django_assert_max_num_queries(14):
        r = client_a.get(reverse("procurement:asn_list"))
        assert r.status_code == 200
        assert len(r.context["object_list"]) == 15
        r.content.decode()


def test_fulfillment_asn_list_never_shows_other_tenant_rows(client_a, fulfillment_asn_draft_a,
                                                            fulfillment_asn_b):
    r = client_a.get(reverse("procurement:asn_list"))
    pks = _fulfillment_pks(r)
    assert fulfillment_asn_draft_a.pk in pks
    assert fulfillment_asn_b.pk not in pks
    # NOT a number-substring check: ``TenantNumbered`` numbers PER TENANT, so A's own notice and
    # B's are BOTH "ASN-00001" and the substring would match A's correctly-rendered row. B's
    # detail PATH carries its pk, so it cannot collide.
    assert reverse("procurement:asn_detail", args=[fulfillment_asn_b.pk])         not in r.content.decode()


# ------------------------------------------------------------------ ASN create


def test_fulfillment_asn_create_get_context(client_a, fulfillment_po_a):
    r = client_a.get(reverse("procurement:asn_create"))
    assert r.status_code == 200
    assert "procurement/orderfulfillment/asn/form.html" in _fulfillment_templates(r)
    assert r.context["is_edit"] is False
    assert r.context["obj"] is None
    assert r.context["formset"] is None
    assert r.context["order"] is None
    form = r.context["form"]
    assert "purchase_order" in form.fields
    assert list(form.fields["purchase_order"].queryset) == [fulfillment_po_a]
    for hidden in ("tenant", "number", "status", "created_by", "delivered_at", "pod_reference"):
        assert hidden not in form.fields


def test_fulfillment_asn_create_post_saves_with_request_tenant(client_a, tenant_a, admin_user,
                                                               fulfillment_po_a):
    body = _fulfillment_asn_header_post(
        purchase_order=str(fulfillment_po_a.pk), supplier_reference="NW-DN-7001",
        source="portal", tracking_number="TRK-7001",
        ship_date=_fulfillment_today().strftime("%Y-%m-%d"),
        expected_delivery_date=(_fulfillment_today() + _fulfillment_days(5)).strftime("%Y-%m-%d"))
    r = client_a.post(reverse("procurement:asn_create"), body, follow=True)
    assert r.status_code == 200

    obj = AdvancedShipmentNotice.objects.get(supplier_reference="NW-DN-7001")
    assert obj.tenant_id == tenant_a.pk
    assert obj.created_by_id == admin_user.pk
    assert obj.number == "ASN-00001"
    assert obj.status == "draft"           # verb-only, never posted
    assert obj.purchase_order_id == fulfillment_po_a.pk
    assert r.redirect_chain[-1][0] == reverse("procurement:asn_detail", args=[obj.pk])

    audit = _fulfillment_audit(AdvancedShipmentNotice, obj, "create")
    assert audit.count() == 1
    assert audit.first().changes["purchase_order"] == fulfillment_po_a.number


def test_fulfillment_asn_create_post_invalid_rerenders_with_errors(client_a, fulfillment_po_a):
    r = client_a.post(reverse("procurement:asn_create"),
                      _fulfillment_asn_header_post(purchase_order=""))
    assert r.status_code == 200
    assert "purchase_order" in r.context["form"].errors
    assert AdvancedShipmentNotice.objects.count() == 0


def test_fulfillment_asn_create_post_ignores_system_fields(client_a, tenant_a, fulfillment_po_a):
    body = _fulfillment_asn_header_post(
        purchase_order=str(fulfillment_po_a.pk), supplier_reference="NW-DN-7002",
        status="delivered", number="ASN-99999", pod_reference="FAKE-POD",
        arrival_condition="refused")
    client_a.post(reverse("procurement:asn_create"), body, follow=True)
    obj = AdvancedShipmentNotice.objects.get(supplier_reference="NW-DN-7002")
    assert obj.status == "draft"
    assert obj.number == "ASN-00001"
    assert obj.pod_reference == "" and obj.arrival_condition == ""


def test_fulfillment_asn_create_duplicate_supplier_reference_is_field_error(
        client_a, fulfillment_asn_draft_a, fulfillment_po_a):
    r = client_a.post(reverse("procurement:asn_create"),
                      _fulfillment_asn_header_post(purchase_order=str(fulfillment_po_a.pk),
                                                   supplier_reference="NW-DN-1001"))
    assert r.status_code == 200
    assert "supplier_reference" in r.context["form"].errors
    assert AdvancedShipmentNotice.objects.count() == 1


# ------------------------------------------------------------------ ASN detail


def test_fulfillment_asn_detail_context_and_action_flags(client_a, fulfillment_asn_draft_a,
                                                         fulfillment_asn_line_a):
    r = client_a.get(reverse("procurement:asn_detail", args=[fulfillment_asn_draft_a.pk]))
    assert r.status_code == 200
    assert "procurement/orderfulfillment/asn/detail.html" in _fulfillment_templates(r)

    ctx = r.context
    assert ctx["obj"].pk == fulfillment_asn_draft_a.pk
    assert [row.pk for row in ctx["lines"]] == [fulfillment_asn_line_a.pk]
    assert ctx["order"].pk == fulfillment_asn_draft_a.purchase_order_id
    assert "arrival_condition" in ctx["confirm_form"].fields
    assert "cancellation_reason" in ctx["cancel_form"].fields
    assert ctx["can_edit"] is True and ctx["can_submit"] is True
    assert ctx["can_mark_in_transit"] is True
    assert ctx["can_confirm"] is False      # a draft is not in flight
    assert ctx["can_cancel"] is True
    assert ctx["can_delete"] is True        # admin_user is a tenant admin, and it is a draft
    assert fulfillment_asn_draft_a.number in r.content.decode()


def test_fulfillment_asn_detail_delivered_row_closes_every_flag(client_a,
                                                                fulfillment_asn_delivered_a):
    r = client_a.get(reverse("procurement:asn_detail", args=[fulfillment_asn_delivered_a.pk]))
    ctx = r.context
    assert ctx["can_edit"] is False and ctx["can_submit"] is False
    assert ctx["can_mark_in_transit"] is False and ctx["can_confirm"] is False
    assert ctx["can_cancel"] is False and ctx["can_delete"] is False
    assert "POD-3004" in r.content.decode()


def test_fulfillment_asn_detail_non_admin_cannot_see_delete(member_client,
                                                            fulfillment_asn_draft_a):
    r = member_client.get(reverse("procurement:asn_detail", args=[fulfillment_asn_draft_a.pk]))
    assert r.status_code == 200
    assert r.context["can_delete"] is False


def test_fulfillment_asn_detail_cross_tenant_pk_is_404(client_a, fulfillment_asn_b):
    assert client_a.get(reverse("procurement:asn_detail",
                                args=[fulfillment_asn_b.pk])).status_code == 404


# ------------------------------------------------------------------ ASN edit


def test_fulfillment_asn_edit_get_drops_order_and_binds_formset(client_a,
                                                                fulfillment_asn_draft_a,
                                                                fulfillment_po_line_a,
                                                                fulfillment_po_line2_a):
    r = client_a.get(reverse("procurement:asn_edit", args=[fulfillment_asn_draft_a.pk]))
    assert r.status_code == 200
    assert "procurement/orderfulfillment/asn/form.html" in _fulfillment_templates(r)
    assert r.context["is_edit"] is True
    assert r.context["obj"].pk == fulfillment_asn_draft_a.pk
    assert r.context["order"].pk == fulfillment_asn_draft_a.purchase_order_id
    assert "purchase_order" not in r.context["form"].fields

    formset = r.context["formset"]
    assert formset.prefix == "lines"
    assert set(formset.forms[0].fields["po_line"].queryset) == {fulfillment_po_line_a,
                                                               fulfillment_po_line2_a}


def test_fulfillment_asn_edit_post_saves_header_and_line(client_a, fulfillment_asn_draft_a,
                                                         fulfillment_po_line_a):
    body = _fulfillment_asn_header_post(
        supplier_reference="NW-DN-1001", source="email", carrier_name="Rhine Logistics",
        tracking_number="TRK-EDIT-1")
    body.update(_fulfillment_line_management(total=1, initial=0))
    body.update({"lines-0-po_line": str(fulfillment_po_line_a.pk),
                 "lines-0-quantity_shipped": "6", "lines-0-item_description": "",
                 "lines-0-sku_hint": "", "lines-0-uom_hint": "", "lines-0-package_ref": "",
                 "lines-0-lot_number": "", "lines-0-serial_number": "",
                 "lines-0-expiry_date": "", "lines-0-country_of_origin": "",
                 "lines-0-notes": "", "lines-0-id": ""})

    r = client_a.post(reverse("procurement:asn_edit", args=[fulfillment_asn_draft_a.pk]),
                      body, follow=True)
    assert r.status_code == 200
    assert r.redirect_chain[-1][0] == reverse("procurement:asn_detail",
                                              args=[fulfillment_asn_draft_a.pk])

    fulfillment_asn_draft_a.refresh_from_db()
    assert fulfillment_asn_draft_a.source == "email"
    assert fulfillment_asn_draft_a.carrier_name == "Rhine Logistics"
    line = AsnLine.objects.get(asn=fulfillment_asn_draft_a)
    assert line.po_line_id == fulfillment_po_line_a.pk
    assert line.quantity_shipped == Decimal("6.0000")
    # blank text is copied from the PO line by AsnLine.save()
    assert line.item_description == fulfillment_po_line_a.item_description

    audit = _fulfillment_audit(AdvancedShipmentNotice, fulfillment_asn_draft_a, "update").first()
    assert audit is not None and audit.changes["lines"] == 1


def test_fulfillment_asn_edit_post_invalid_line_rerenders(client_a, fulfillment_asn_draft_a,
                                                          fulfillment_po_line_a):
    body = _fulfillment_asn_header_post(supplier_reference="NW-DN-1001")
    body.update(_fulfillment_line_management(total=1, initial=0))
    body.update({"lines-0-po_line": str(fulfillment_po_line_a.pk),
                 "lines-0-quantity_shipped": "0", "lines-0-id": ""})
    r = client_a.post(reverse("procurement:asn_edit", args=[fulfillment_asn_draft_a.pk]), body)
    assert r.status_code == 200
    assert r.context["formset"].errors[0]
    assert AsnLine.objects.count() == 0


def test_fulfillment_asn_edit_refused_once_delivered(client_a, fulfillment_asn_delivered_a):
    r = client_a.get(reverse("procurement:asn_edit", args=[fulfillment_asn_delivered_a.pk]),
                     follow=True)
    assert r.redirect_chain[-1][0] == reverse("procurement:asn_detail",
                                              args=[fulfillment_asn_delivered_a.pk])
    assert any("can no longer be edited" in m for m in _fulfillment_messages(r))


def test_fulfillment_asn_edit_cross_tenant_pk_is_404(client_a, fulfillment_asn_b):
    assert client_a.get(reverse("procurement:asn_edit",
                                args=[fulfillment_asn_b.pk])).status_code == 404


# ------------------------------------------------------------------ ASN delete


def test_fulfillment_asn_delete_get_is_405_and_row_survives(client_a, fulfillment_asn_draft_a):
    r = client_a.get(reverse("procurement:asn_delete", args=[fulfillment_asn_draft_a.pk]))
    assert r.status_code == 405
    assert AdvancedShipmentNotice.objects.filter(pk=fulfillment_asn_draft_a.pk).exists()


def test_fulfillment_asn_delete_post_removes_draft(client_a, fulfillment_asn_draft_a):
    pk = fulfillment_asn_draft_a.pk
    r = client_a.post(reverse("procurement:asn_delete", args=[pk]), follow=True)
    assert r.redirect_chain[-1][0] == reverse("procurement:asn_list")
    assert not AdvancedShipmentNotice.objects.filter(pk=pk).exists()
    assert _fulfillment_audit(AdvancedShipmentNotice, fulfillment_asn_draft_a, "delete").exists()


def test_fulfillment_asn_delete_refuses_non_draft(client_a, fulfillment_asn_in_transit_a):
    pk = fulfillment_asn_in_transit_a.pk
    r = client_a.post(reverse("procurement:asn_delete", args=[pk]), follow=True)
    assert r.redirect_chain[-1][0] == reverse("procurement:asn_detail", args=[pk])
    assert any("Only a draft ASN can be deleted" in m for m in _fulfillment_messages(r))
    assert AdvancedShipmentNotice.objects.filter(pk=pk).exists()


# ------------------------------------------------------------------ ASN lifecycle verbs


@pytest.mark.parametrize("name", ["asn_submit", "asn_mark_in_transit", "asn_confirm_delivery",
                                  "asn_cancel"])
def test_fulfillment_asn_verb_get_is_405(client_a, fulfillment_asn_draft_a, name):
    r = client_a.get(reverse("procurement:%s" % name, args=[fulfillment_asn_draft_a.pk]))
    assert r.status_code == 405
    fulfillment_asn_draft_a.refresh_from_db()
    assert fulfillment_asn_draft_a.status == "draft"


def test_fulfillment_asn_submit_moves_draft_then_noops(client_a, fulfillment_asn_draft_a):
    url = reverse("procurement:asn_submit", args=[fulfillment_asn_draft_a.pk])
    r = client_a.post(url, follow=True)
    fulfillment_asn_draft_a.refresh_from_db()
    assert fulfillment_asn_draft_a.status == "submitted"
    assert fulfillment_asn_draft_a.submitted_at is not None
    assert any("submitted" in m for m in _fulfillment_messages(r))
    stamped = fulfillment_asn_draft_a.submitted_at

    r2 = client_a.post(url, follow=True)
    fulfillment_asn_draft_a.refresh_from_db()
    assert fulfillment_asn_draft_a.submitted_at == stamped
    assert any("already" in m for m in _fulfillment_messages(r2))


def test_fulfillment_asn_mark_in_transit_backfills_submitted_at(client_a,
                                                                fulfillment_asn_draft_a):
    client_a.post(reverse("procurement:asn_mark_in_transit",
                          args=[fulfillment_asn_draft_a.pk]), follow=True)
    fulfillment_asn_draft_a.refresh_from_db()
    assert fulfillment_asn_draft_a.status == "in_transit"
    assert fulfillment_asn_draft_a.submitted_at is not None


def test_fulfillment_asn_confirm_delivery_stamps_pod(client_a, admin_user,
                                                     fulfillment_asn_in_transit_a):
    url = reverse("procurement:asn_confirm_delivery", args=[fulfillment_asn_in_transit_a.pk])
    r = client_a.post(url, {"arrival_condition": "damaged", "pod_reference": "POD-7788",
                            "received_signature_name": "A. Receiver", "delivered_at": ""},
                      follow=True)
    assert r.redirect_chain[-1][0] == reverse("procurement:asn_detail",
                                              args=[fulfillment_asn_in_transit_a.pk])
    fulfillment_asn_in_transit_a.refresh_from_db()
    assert fulfillment_asn_in_transit_a.status == "delivered"
    assert fulfillment_asn_in_transit_a.arrival_condition == "damaged"
    assert fulfillment_asn_in_transit_a.pod_reference == "POD-7788"
    assert fulfillment_asn_in_transit_a.received_signature_name == "A. Receiver"
    assert fulfillment_asn_in_transit_a.confirmed_by_id == admin_user.pk
    changes = _fulfillment_audit(AdvancedShipmentNotice, fulfillment_asn_in_transit_a,
                                 "update").first().changes
    assert changes["action"] == "confirm_delivery" and changes["condition"] == "damaged"


def test_fulfillment_asn_confirm_delivery_returns_to_board_tab(client_a, fulfillment_asn_late_a):
    r = client_a.post(reverse("procurement:asn_confirm_delivery",
                              args=[fulfillment_asn_late_a.pk]),
                      {"arrival_condition": "good", "next": "confirmation", "due": "overdue"})
    assert r.status_code == 302
    assert r["Location"] == "%s?due=overdue" % reverse("procurement:delivery_confirmation")
    fulfillment_asn_late_a.refresh_from_db()
    assert fulfillment_asn_late_a.status == "delivered"


def test_fulfillment_asn_confirm_delivery_drops_unknown_bucket(client_a, fulfillment_asn_late_a):
    r = client_a.post(reverse("procurement:asn_confirm_delivery",
                              args=[fulfillment_asn_late_a.pk]),
                      {"arrival_condition": "good", "next": "confirmation", "due": "zzz"})
    assert r["Location"] == reverse("procurement:delivery_confirmation")


def test_fulfillment_asn_confirm_delivery_double_submit_does_not_restamp(
        client_a, fulfillment_asn_in_transit_a):
    url = reverse("procurement:asn_confirm_delivery", args=[fulfillment_asn_in_transit_a.pk])
    client_a.post(url, {"arrival_condition": "good", "pod_reference": "POD-FIRST"}, follow=True)
    fulfillment_asn_in_transit_a.refresh_from_db()
    first_moment = fulfillment_asn_in_transit_a.delivered_at

    r = client_a.post(url, {"arrival_condition": "refused", "pod_reference": "POD-SECOND"},
                      follow=True)
    fulfillment_asn_in_transit_a.refresh_from_db()
    assert fulfillment_asn_in_transit_a.delivered_at == first_moment
    assert fulfillment_asn_in_transit_a.pod_reference == "POD-FIRST"
    assert fulfillment_asn_in_transit_a.arrival_condition == "good"
    assert any("nothing to confirm" in m for m in _fulfillment_messages(r))


def test_fulfillment_asn_cancel_requires_a_reason(client_a, fulfillment_asn_draft_a):
    r = client_a.post(reverse("procurement:asn_cancel", args=[fulfillment_asn_draft_a.pk]),
                      {"cancellation_reason": "   "}, follow=True)
    assert any("Give a reason" in m for m in _fulfillment_messages(r))
    fulfillment_asn_draft_a.refresh_from_db()
    assert fulfillment_asn_draft_a.status == "draft"


def test_fulfillment_asn_cancel_records_reason(client_a, fulfillment_asn_draft_a):
    r = client_a.post(reverse("procurement:asn_cancel", args=[fulfillment_asn_draft_a.pk]),
                      {"cancellation_reason": "Supplier withdrew the notice."}, follow=True)
    assert r.status_code == 200
    fulfillment_asn_draft_a.refresh_from_db()
    assert fulfillment_asn_draft_a.status == "cancelled"
    assert fulfillment_asn_draft_a.cancellation_reason == "Supplier withdrew the notice."
    assert fulfillment_asn_draft_a.cancelled_at is not None


def test_fulfillment_asn_cancel_refused_once_delivered(client_a, fulfillment_asn_delivered_a):
    r = client_a.post(reverse("procurement:asn_cancel", args=[fulfillment_asn_delivered_a.pk]),
                      {"cancellation_reason": "Too late."}, follow=True)
    assert any("cannot be cancelled" in m for m in _fulfillment_messages(r))
    fulfillment_asn_delivered_a.refresh_from_db()
    assert fulfillment_asn_delivered_a.status == "delivered"


# ================================================================== delivery schedules


def test_fulfillment_schedule_list_renders_contract_context(client_a, fulfillment_schedule_a,
                                                            fulfillment_schedule_late_a,
                                                            fulfillment_po_a):
    r = client_a.get(reverse("procurement:deliveryschedule_list"))
    assert r.status_code == 200
    assert "procurement/orderfulfillment/deliveryschedule/list.html" in _fulfillment_templates(r)

    ctx = r.context
    assert {o.pk for o in ctx["object_list"]} == {fulfillment_schedule_a.pk,
                                                  fulfillment_schedule_late_a.pk}
    assert ctx["page_obj"].paginator.count == 2
    assert ctx["q"] == ""
    assert [v for v, _ in ctx["status_choices"]] == ["planned", "confirmed", "shipped",
                                                     "received", "cancelled"]
    assert [v for v, _ in ctx["mode_choices"]] == ["standard", "express", "courier", "freight",
                                                   "collection", "dropship"]
    assert [o.pk for o in ctx["purchase_orders"]] == [fulfillment_po_a.pk]
    assert ctx["stats"] == {"total": 2, "open": 2, "late": 1, "received": 0}
    # the coverage annotation the template's coverage_pct column reads
    assert all(getattr(o, "sched_total_annot", None) == Decimal("7")
               for o in ctx["object_list"])
    assert fulfillment_schedule_a.number in r.content.decode()


def test_fulfillment_schedule_list_search_and_filters(client_a, fulfillment_schedule_a,
                                                      fulfillment_schedule_late_a,
                                                      fulfillment_po_a):
    url = reverse("procurement:deliveryschedule_list")

    r = client_a.get(url, {"q": fulfillment_schedule_late_a.number})
    assert _fulfillment_pks(r) == [fulfillment_schedule_late_a.pk]

    r = client_a.get(url, {"q": "Bearing housing"})
    assert len(_fulfillment_pks(r)) == 2

    r = client_a.get(url, {"q": fulfillment_po_a.number})
    assert len(_fulfillment_pks(r)) == 2

    r = client_a.get(url, {"mode": "express"})
    assert _fulfillment_pks(r) == [fulfillment_schedule_late_a.pk]

    r = client_a.get(url, {"status": "planned"})
    assert len(_fulfillment_pks(r)) == 2
    r = client_a.get(url, {"status": "received"})
    assert _fulfillment_pks(r) == []

    r = client_a.get(url, {"po": str(fulfillment_po_a.pk)})
    assert len(_fulfillment_pks(r)) == 2


def test_fulfillment_schedule_list_late_flag(client_a, fulfillment_schedule_a,
                                             fulfillment_schedule_late_a):
    r = client_a.get(reverse("procurement:deliveryschedule_list"), {"late": "1"})
    assert _fulfillment_pks(r) == [fulfillment_schedule_late_a.pk]
    assert r.context["page_obj"].paginator.count == 1
    assert r.context["stats"]["total"] == 2


@pytest.mark.parametrize("params", [
    {"po": "abc"}, {"po": "99999999999999999999999"}, {"status": "zzz"}, {"mode": "zzz"},
    {"late": "yes"}, {"page": "abc"},
])
def test_fulfillment_schedule_list_junk_params_never_500(client_a, fulfillment_schedule_a,
                                                         params):
    r = client_a.get(reverse("procurement:deliveryschedule_list"), params)
    assert r.status_code == 200 and "object_list" in r.context


def test_fulfillment_schedule_list_pagination_page_two(client_a, tenant_a,
                                                       fulfillment_po_line2_a):
    _fulfillment_bulk_schedules(tenant_a, fulfillment_po_line2_a, 17)
    url = reverse("procurement:deliveryschedule_list")

    first = client_a.get(url)
    assert len(first.context["object_list"]) == 15
    assert first.context["page_obj"].paginator.num_pages == 2

    second = client_a.get(url, {"page": "2"})
    assert len(second.context["object_list"]) == 2
    assert second.context["page_obj"].number == 2

    past = client_a.get(url, {"page": "500"})
    assert past.status_code == 200 and past.context["page_obj"].number == 2


def test_fulfillment_schedule_list_query_count_is_bounded(client_a, tenant_a, org_unit_a,
                                                          fulfillment_po_line2_a,
                                                          fulfillment_asn_draft_a,
                                                          django_assert_max_num_queries):
    rows = _fulfillment_bulk_schedules(tenant_a, fulfillment_po_line2_a, 15)
    # asn.__str__ hops to purchase_order.number — the chained __str__ FK hop the view
    # select_relates specifically for.
    DeliverySchedule.objects.filter(pk__in=[r.pk for r in rows]).update(
        asn=fulfillment_asn_draft_a, ship_to=org_unit_a)
    with django_assert_max_num_queries(14):
        r = client_a.get(reverse("procurement:deliveryschedule_list"))
        assert r.status_code == 200
        assert len(r.context["object_list"]) == 15
        r.content.decode()


def test_fulfillment_schedule_list_never_shows_other_tenant_rows(client_a,
                                                                 fulfillment_schedule_a,
                                                                 fulfillment_schedule_b):
    r = client_a.get(reverse("procurement:deliveryschedule_list"))
    assert _fulfillment_pks(r) == [fulfillment_schedule_a.pk]
    # Per-tenant numbering makes both rows "DSC-00001" — assert on the pk-bearing URL instead.
    assert reverse("procurement:deliveryschedule_detail", args=[fulfillment_schedule_b.pk])         not in r.content.decode()


# ------------------------------------------------------------------ schedule create


def test_fulfillment_schedule_create_get_context_and_prefill(client_a, fulfillment_po_line_a):
    url = reverse("procurement:deliveryschedule_create")
    r = client_a.get(url)
    assert r.status_code == 200
    assert ("procurement/orderfulfillment/deliveryschedule/form.html"
            in _fulfillment_templates(r))
    assert r.context["is_edit"] is False and r.context["obj"] is None
    form = r.context["form"]
    assert "status" in form.fields          # deliberately form-editable on this model
    for hidden in ("tenant", "number", "created_by"):
        assert hidden not in form.fields

    r = client_a.get(url, {"po_line": str(fulfillment_po_line_a.pk)})
    assert r.context["form"].initial["po_line"] == fulfillment_po_line_a.pk


@pytest.mark.parametrize("raw", ["abc", "999999999999999999999999", "-1", ""])
def test_fulfillment_schedule_create_drops_junk_prefill(client_a, fulfillment_po_line_a, raw):
    r = client_a.get(reverse("procurement:deliveryschedule_create"), {"po_line": raw})
    assert r.status_code == 200
    assert "po_line" not in r.context["form"].initial


def test_fulfillment_schedule_create_drops_foreign_prefill(client_a, fulfillment_po_line_b):
    r = client_a.get(reverse("procurement:deliveryschedule_create"),
                     {"po_line": str(fulfillment_po_line_b.pk)})
    assert r.status_code == 200
    assert "po_line" not in r.context["form"].initial


def test_fulfillment_schedule_create_post_saves_with_request_tenant(client_a, tenant_a,
                                                                    admin_user,
                                                                    fulfillment_po_line2_a,
                                                                    org_unit_a):
    body = _fulfillment_schedule_post(po_line=str(fulfillment_po_line2_a.pk),
                                      scheduled_quantity="2", ship_to=str(org_unit_a.pk),
                                      delivery_mode="courier")
    r = client_a.post(reverse("procurement:deliveryschedule_create"), body, follow=True)
    assert r.status_code == 200

    obj = DeliverySchedule.objects.get(po_line=fulfillment_po_line2_a)
    assert obj.tenant_id == tenant_a.pk
    assert obj.created_by_id == admin_user.pk
    assert obj.number == "DSC-00001"
    assert obj.scheduled_quantity == Decimal("2.0000")
    assert obj.ship_to_id == org_unit_a.pk
    assert r.redirect_chain[-1][0] == reverse("procurement:deliveryschedule_detail",
                                              args=[obj.pk])
    assert _fulfillment_audit(DeliverySchedule, obj, "create").count() == 1


def test_fulfillment_schedule_create_over_commitment_is_field_error(client_a,
                                                                    fulfillment_po_line2_a,
                                                                    tenant_a):
    # the line orders 4; commit all of it, then try to add one more instalment
    DeliverySchedule.objects.create(tenant=tenant_a, po_line=fulfillment_po_line2_a,
                                    sequence=1, scheduled_quantity=Decimal("4"),
                                    need_by_date=_fulfillment_today())
    body = _fulfillment_schedule_post(po_line=str(fulfillment_po_line2_a.pk), sequence="2",
                                      scheduled_quantity="1")
    r = client_a.post(reverse("procurement:deliveryschedule_create"), body)
    assert r.status_code == 200
    assert "scheduled_quantity" in r.context["form"].errors
    assert "over-commit" in str(r.context["form"].errors["scheduled_quantity"])
    assert DeliverySchedule.objects.count() == 1


def test_fulfillment_schedule_create_post_invalid_rerenders(client_a):
    r = client_a.post(reverse("procurement:deliveryschedule_create"),
                      _fulfillment_schedule_post(po_line="", need_by_date=""))
    assert r.status_code == 200
    assert "po_line" in r.context["form"].errors
    assert "need_by_date" in r.context["form"].errors
    assert DeliverySchedule.objects.count() == 0


# ------------------------------------------------------------------ split console


def test_fulfillment_schedule_split_get_context_has_no_object_list(client_a,
                                                                   fulfillment_po_line_a,
                                                                   fulfillment_po_line2_a):
    r = client_a.get(reverse("procurement:deliveryschedule_split"))
    assert r.status_code == 200
    assert ("procurement/orderfulfillment/deliveryschedule/split.html"
            in _fulfillment_templates(r))
    assert r.context["is_edit"] is False and r.context["obj"] is None
    assert set(f for f in r.context["form"].fields) == {"po_line", "instalments", "first_date",
                                                        "interval_days"}
    assert {line.pk for line in r.context["po_lines"]} == {fulfillment_po_line_a.pk,
                                                           fulfillment_po_line2_a.pk}
    assert all(hasattr(line, "scheduled_total") for line in r.context["po_lines"])
    # NOT a crud_list view — the split console paginates nothing
    assert "object_list" not in r.context
    assert "page_obj" not in r.context


def test_fulfillment_schedule_split_post_creates_instalments(client_a, tenant_a, admin_user,
                                                             fulfillment_po_line2_a,
                                                             fulfillment_po_a):
    first = _fulfillment_today() + _fulfillment_days(3)
    r = client_a.post(reverse("procurement:deliveryschedule_split"),
                      {"po_line": str(fulfillment_po_line2_a.pk), "instalments": "3",
                       "first_date": first.strftime("%Y-%m-%d"), "interval_days": "7"},
                      follow=True)
    assert r.status_code == 200
    assert r.redirect_chain[-1][0] == "%s?po=%s" % (
        reverse("procurement:deliveryschedule_list"), fulfillment_po_a.pk)

    rows = list(DeliverySchedule.objects.filter(po_line=fulfillment_po_line2_a)
                .order_by("sequence"))
    assert len(rows) == 3
    assert [row.sequence for row in rows] == [1, 2, 3]
    assert sum(row.scheduled_quantity for row in rows) == Decimal("4.0000")
    assert [row.need_by_date for row in rows] == [first, first + _fulfillment_days(7),
                                                  first + _fulfillment_days(14)]
    assert all(row.tenant_id == tenant_a.pk for row in rows)
    assert all(row.created_by_id == admin_user.pk for row in rows)
    assert all(row.change_reason == "Auto-split into 3 instalments" for row in rows)
    assert AuditLog.objects.filter(
        content_type=ContentType.objects.get_for_model(DeliverySchedule),
        action="create").count() == 3
    assert any("3 delivery instalments created" in m for m in _fulfillment_messages(r))


def test_fulfillment_schedule_split_fully_covered_line_is_non_field_error(
        client_a, tenant_a, fulfillment_po_line2_a):
    DeliverySchedule.objects.create(tenant=tenant_a, po_line=fulfillment_po_line2_a,
                                    sequence=1, scheduled_quantity=Decimal("4"),
                                    need_by_date=_fulfillment_today())
    r = client_a.post(reverse("procurement:deliveryschedule_split"),
                      {"po_line": str(fulfillment_po_line2_a.pk), "instalments": "2",
                       "first_date": _fulfillment_today().strftime("%Y-%m-%d"),
                       "interval_days": "7"})
    assert r.status_code == 200
    assert "already fully covered" in str(r.context["form"].non_field_errors())
    assert DeliverySchedule.objects.count() == 1


@pytest.mark.parametrize("payload,field", [
    ({"instalments": "1"}, "instalments"),
    ({"instalments": "13"}, "instalments"),
    ({"instalments": "abc"}, "instalments"),
    ({"interval_days": "0"}, "interval_days"),
    ({"first_date": ""}, "first_date"),
    ({"po_line": ""}, "po_line"),
])
def test_fulfillment_schedule_split_rejects_bad_input(client_a, fulfillment_po_line2_a,
                                                      payload, field):
    body = {"po_line": str(fulfillment_po_line2_a.pk), "instalments": "3",
            "first_date": _fulfillment_today().strftime("%Y-%m-%d"), "interval_days": "7"}
    body.update(payload)
    r = client_a.post(reverse("procurement:deliveryschedule_split"), body)
    assert r.status_code == 200
    assert field in r.context["form"].errors
    assert DeliverySchedule.objects.count() == 0


# ------------------------------------------------------------------ schedule detail/edit/delete


def test_fulfillment_schedule_detail_context_and_coverage(client_a, fulfillment_schedule_a,
                                                          fulfillment_schedule_late_a,
                                                          fulfillment_po_line_a,
                                                          fulfillment_po_a):
    r = client_a.get(reverse("procurement:deliveryschedule_detail",
                             args=[fulfillment_schedule_a.pk]))
    assert r.status_code == 200
    assert ("procurement/orderfulfillment/deliveryschedule/detail.html"
            in _fulfillment_templates(r))
    ctx = r.context
    assert ctx["obj"].pk == fulfillment_schedule_a.pk
    assert ctx["po_line"].pk == fulfillment_po_line_a.pk
    assert ctx["order"].pk == fulfillment_po_a.pk
    assert [s.pk for s in ctx["siblings"]] == [fulfillment_schedule_a.pk,
                                               fulfillment_schedule_late_a.pk]
    assert ctx["scheduled_total"] == Decimal("7")
    assert ctx["remaining_quantity"] == Decimal("3")
    assert ctx["coverage_pct"] == 70
    assert ctx["is_under_covered"] is True
    assert fulfillment_schedule_a.number in r.content.decode()


def test_fulfillment_schedule_detail_cross_tenant_pk_is_404(client_a, fulfillment_schedule_b):
    assert client_a.get(reverse("procurement:deliveryschedule_detail",
                                args=[fulfillment_schedule_b.pk])).status_code == 404


def test_fulfillment_schedule_edit_get_and_post(client_a, fulfillment_schedule_a):
    url = reverse("procurement:deliveryschedule_edit", args=[fulfillment_schedule_a.pk])
    r = client_a.get(url)
    assert r.status_code == 200
    assert ("procurement/orderfulfillment/deliveryschedule/form.html"
            in _fulfillment_templates(r))
    assert r.context["is_edit"] is True
    assert r.context["obj"].pk == fulfillment_schedule_a.pk

    body = _fulfillment_schedule_post(
        po_line=str(fulfillment_schedule_a.po_line_id), sequence="1",
        scheduled_quantity="5", status="confirmed", delivery_mode="freight",
        need_by_date=(_fulfillment_today() + _fulfillment_days(11)).strftime("%Y-%m-%d"),
        change_reason="Supplier consolidated the drop")
    r = client_a.post(url, body, follow=True)
    assert r.redirect_chain[-1][0] == reverse("procurement:deliveryschedule_detail",
                                              args=[fulfillment_schedule_a.pk])
    fulfillment_schedule_a.refresh_from_db()
    assert fulfillment_schedule_a.scheduled_quantity == Decimal("5.0000")
    assert fulfillment_schedule_a.status == "confirmed"
    assert fulfillment_schedule_a.delivery_mode == "freight"
    assert _fulfillment_audit(DeliverySchedule, fulfillment_schedule_a, "update").exists()


def test_fulfillment_schedule_edit_cross_tenant_pk_is_404(client_a, fulfillment_schedule_b):
    assert client_a.get(reverse("procurement:deliveryschedule_edit",
                                args=[fulfillment_schedule_b.pk])).status_code == 404


def test_fulfillment_schedule_delete_get_is_405_and_row_survives(client_a,
                                                                 fulfillment_schedule_a):
    r = client_a.get(reverse("procurement:deliveryschedule_delete",
                             args=[fulfillment_schedule_a.pk]))
    assert r.status_code == 405
    assert DeliverySchedule.objects.filter(pk=fulfillment_schedule_a.pk).exists()


def test_fulfillment_schedule_delete_post_removes_row_for_any_member(member_client,
                                                                     fulfillment_schedule_a):
    pk = fulfillment_schedule_a.pk
    r = member_client.post(reverse("procurement:deliveryschedule_delete", args=[pk]),
                           follow=True)
    assert r.redirect_chain[-1][0] == reverse("procurement:deliveryschedule_list")
    assert not DeliverySchedule.objects.filter(pk=pk).exists()
    assert _fulfillment_audit(DeliverySchedule, fulfillment_schedule_a, "delete").exists()


# ================================================================== backorders


def test_fulfillment_backorder_list_renders_contract_context(client_a,
                                                             fulfillment_backorder_open_a,
                                                             fulfillment_backorder_past_due_a,
                                                             fulfillment_backorder_closed_a,
                                                             fulfillment_po_a):
    r = client_a.get(reverse("procurement:backorder_list"))
    assert r.status_code == 200
    assert "procurement/orderfulfillment/backorder/list.html" in _fulfillment_templates(r)

    ctx = r.context
    assert len(ctx["object_list"]) == 3
    assert ctx["page_obj"].paginator.count == 3
    assert ctx["q"] == ""
    assert [v for v, _ in ctx["status_choices"]] == ["open", "rescheduled", "fulfilled",
                                                     "cancelled"]
    assert "out_of_stock" in [v for v, _ in ctx["reason_choices"]]
    assert [v for v, _ in ctx["risk_choices"]] == ["past_due", "at_risk", "no_commitment",
                                                   "on_track"]
    assert [o.pk for o in ctx["purchase_orders"]] == [fulfillment_po_a.pk]
    assert ctx["stats"] == {"open": 2, "past_due": 1, "at_risk": 1, "no_commitment": 0}
    assert fulfillment_backorder_open_a.number in r.content.decode()


def test_fulfillment_backorder_list_search_and_filters(client_a, fulfillment_backorder_open_a,
                                                       fulfillment_backorder_past_due_a,
                                                       fulfillment_po_a):
    url = reverse("procurement:backorder_list")

    r = client_a.get(url, {"q": fulfillment_backorder_past_due_a.number})
    assert _fulfillment_pks(r) == [fulfillment_backorder_past_due_a.pk]

    r = client_a.get(url, {"q": "Drive belt"})
    assert _fulfillment_pks(r) == [fulfillment_backorder_past_due_a.pk]

    r = client_a.get(url, {"q": fulfillment_po_a.number})
    assert len(_fulfillment_pks(r)) == 2

    r = client_a.get(url, {"status": "open"})
    assert len(_fulfillment_pks(r)) == 2

    r = client_a.get(url, {"reason": "production_delay"})
    assert _fulfillment_pks(r) == [fulfillment_backorder_past_due_a.pk]

    r = client_a.get(url, {"po": str(fulfillment_po_a.pk)})
    assert len(_fulfillment_pks(r)) == 2


def test_fulfillment_backorder_list_risk_buckets(client_a, fulfillment_backorder_open_a,
                                                 fulfillment_backorder_past_due_a,
                                                 fulfillment_backorder_closed_a):
    url = reverse("procurement:backorder_list")
    r = client_a.get(url, {"risk": "past_due"})
    assert _fulfillment_pks(r) == [fulfillment_backorder_past_due_a.pk]

    r = client_a.get(url, {"risk": "at_risk"})
    assert _fulfillment_pks(r) == [fulfillment_backorder_open_a.pk]

    r = client_a.get(url, {"risk": "no_commitment"})
    assert _fulfillment_pks(r) == []

    # an unknown bucket is IGNORED — 200 with the whole register, never an empty-looking lie
    r = client_a.get(url, {"risk": "zzz"})
    assert r.status_code == 200 and len(_fulfillment_pks(r)) == 3


@pytest.mark.parametrize("params", [
    {"po": "abc"}, {"po": "9999999999999999999999"}, {"status": "zzz"}, {"reason": "zzz"},
    {"risk": "999"}, {"page": "abc"},
])
def test_fulfillment_backorder_list_junk_params_never_500(client_a,
                                                          fulfillment_backorder_open_a, params):
    r = client_a.get(reverse("procurement:backorder_list"), params)
    assert r.status_code == 200 and "object_list" in r.context


def test_fulfillment_backorder_list_pagination_page_two(client_a, tenant_a,
                                                        fulfillment_po_line_a):
    _fulfillment_bulk_backorders(tenant_a, fulfillment_po_line_a, 16)
    url = reverse("procurement:backorder_list")

    first = client_a.get(url)
    assert len(first.context["object_list"]) == 15
    assert first.context["page_obj"].paginator.num_pages == 2

    second = client_a.get(url, {"page": "2"})
    assert len(second.context["object_list"]) == 1
    assert second.context["page_obj"].number == 2

    past = client_a.get(url, {"page": "77"})
    assert past.status_code == 200 and past.context["page_obj"].number == 2


def test_fulfillment_backorder_list_query_count_is_bounded(client_a, tenant_a,
                                                           fulfillment_po_line_a,
                                                           django_assert_max_num_queries):
    # Backorder.__str__ walks po_line -> purchase_order.number; without select_related that is
    # two extra queries per row.
    _fulfillment_bulk_backorders(tenant_a, fulfillment_po_line_a, 15)
    with django_assert_max_num_queries(14):
        r = client_a.get(reverse("procurement:backorder_list"))
        assert r.status_code == 200
        assert len(r.context["object_list"]) == 15
        r.content.decode()


def test_fulfillment_backorder_list_never_shows_other_tenant_rows(client_a,
                                                                  fulfillment_backorder_open_a,
                                                                  fulfillment_backorder_b):
    r = client_a.get(reverse("procurement:backorder_list"))
    assert _fulfillment_pks(r) == [fulfillment_backorder_open_a.pk]
    # Per-tenant numbering makes both rows "BKO-00001" — assert on the pk-bearing URL instead.
    assert reverse("procurement:backorder_detail", args=[fulfillment_backorder_b.pk])         not in r.content.decode()


# ------------------------------------------------------------------ backorder create


def test_fulfillment_backorder_create_get_context_and_prefill(client_a, fulfillment_po_line_a,
                                                              fulfillment_asn_draft_a):
    url = reverse("procurement:backorder_create")
    r = client_a.get(url)
    assert r.status_code == 200
    assert "procurement/orderfulfillment/backorder/form.html" in _fulfillment_templates(r)
    assert r.context["is_edit"] is False and r.context["obj"] is None
    form = r.context["form"]
    assert "revised_promise_date" in form.fields          # present on CREATE
    for hidden in ("tenant", "number", "status", "reschedule_count", "closed_at",
                   "closure_note", "alert", "created_by"):
        assert hidden not in form.fields

    r = client_a.get(url, {"po_line": str(fulfillment_po_line_a.pk),
                           "asn": str(fulfillment_asn_draft_a.pk), "quantity": "2.5"})
    initial = r.context["form"].initial
    assert initial["po_line"] == fulfillment_po_line_a.pk
    assert initial["asn"] == fulfillment_asn_draft_a.pk
    assert initial["quantity_backordered"] == Decimal("2.5")


@pytest.mark.parametrize("raw", ["NaN", "nan", "Infinity", "-Infinity", "-5", "0", "abc",
                                 "1e400", "99999999999999999999999999999999", "  "])
def test_fulfillment_backorder_create_bad_quantity_prefill_never_500(client_a,
                                                                     fulfillment_po_line_a, raw):
    r = client_a.get(reverse("procurement:backorder_create"),
                     {"po_line": str(fulfillment_po_line_a.pk), "quantity": raw})
    assert r.status_code == 200
    assert "quantity_backordered" not in r.context["form"].initial
    assert r.context["form"].initial["po_line"] == fulfillment_po_line_a.pk


@pytest.mark.parametrize("raw", ["abc", "999999999999999999999999", "-2"])
def test_fulfillment_backorder_create_junk_fk_prefill_is_dropped(client_a, raw):
    r = client_a.get(reverse("procurement:backorder_create"), {"po_line": raw, "asn": raw})
    assert r.status_code == 200
    assert r.context["form"].initial == {}


def test_fulfillment_backorder_create_foreign_prefill_is_dropped(client_a,
                                                                 fulfillment_po_line_b,
                                                                 fulfillment_asn_b):
    r = client_a.get(reverse("procurement:backorder_create"),
                     {"po_line": str(fulfillment_po_line_b.pk),
                      "asn": str(fulfillment_asn_b.pk)})
    assert r.status_code == 200
    assert r.context["form"].initial == {}


def test_fulfillment_backorder_create_post_saves_with_request_tenant(client_a, tenant_a,
                                                                     admin_user,
                                                                     fulfillment_po_line_a):
    body = _fulfillment_backorder_post(
        po_line=str(fulfillment_po_line_a.pk), quantity_backordered="4",
        reason="supplier_capacity",
        revised_promise_date=(_fulfillment_today() + _fulfillment_days(5)).strftime("%Y-%m-%d"))
    r = client_a.post(reverse("procurement:backorder_create"), body, follow=True)
    assert r.status_code == 200

    obj = Backorder.objects.get(po_line=fulfillment_po_line_a)
    assert obj.tenant_id == tenant_a.pk
    assert obj.created_by_id == admin_user.pk
    assert obj.number == "BKO-00001"
    assert obj.status == "open"            # verb-only
    assert obj.reschedule_count == 0
    assert obj.quantity_backordered == Decimal("4.0000")
    assert r.redirect_chain[-1][0] == reverse("procurement:backorder_detail", args=[obj.pk])
    changes = _fulfillment_audit(Backorder, obj, "create").first().changes
    # Compared as a NUMBER, not a string: the audit records the submitted Decimal("4"), while the
    # column stores 4.0000. Both are correct, and asserting the DB's trailing zeros here would be
    # testing decimal formatting rather than "the create was audited with the right quantity".
    assert Decimal(changes["quantity"]) == Decimal("4")


def test_fulfillment_backorder_create_over_ordered_quantity_is_error(client_a,
                                                                     fulfillment_po_line2_a):
    body = _fulfillment_backorder_post(po_line=str(fulfillment_po_line2_a.pk),
                                       quantity_backordered="99")
    r = client_a.post(reverse("procurement:backorder_create"), body)
    assert r.status_code == 200
    assert r.context["form"].errors
    assert Backorder.objects.count() == 0


# ------------------------------------------------------------------ backorder detail/edit


def test_fulfillment_backorder_detail_context_keys(client_a, fulfillment_backorder_open_a,
                                                   fulfillment_po_line_a, fulfillment_po_a):
    r = client_a.get(reverse("procurement:backorder_detail",
                             args=[fulfillment_backorder_open_a.pk]))
    assert r.status_code == 200
    assert "procurement/orderfulfillment/backorder/detail.html" in _fulfillment_templates(r)
    ctx = r.context
    assert ctx["obj"].pk == fulfillment_backorder_open_a.pk
    assert ctx["po_line"].pk == fulfillment_po_line_a.pk
    assert ctx["order"].pk == fulfillment_po_a.pk
    assert "revised_promise_date" in ctx["reschedule_form"].fields
    assert "closure_note" in ctx["close_form"].fields
    assert ctx["alert"] is None
    assert ctx["can_edit"] and ctx["can_reschedule"] and ctx["can_fulfil"]
    assert ctx["can_cancel"] and ctx["can_raise_alert"]
    assert ctx["can_delete"] is True
    assert fulfillment_backorder_open_a.number in r.content.decode()


def test_fulfillment_backorder_detail_closed_row_closes_flags(client_a,
                                                              fulfillment_backorder_closed_a):
    ctx = client_a.get(reverse("procurement:backorder_detail",
                               args=[fulfillment_backorder_closed_a.pk])).context
    assert ctx["can_edit"] is False and ctx["can_reschedule"] is False
    assert ctx["can_fulfil"] is False and ctx["can_cancel"] is False
    assert ctx["can_raise_alert"] is False


def test_fulfillment_backorder_detail_member_cannot_delete(member_client,
                                                           fulfillment_backorder_open_a):
    r = member_client.get(reverse("procurement:backorder_detail",
                                  args=[fulfillment_backorder_open_a.pk]))
    assert r.status_code == 200 and r.context["can_delete"] is False


def test_fulfillment_backorder_detail_cross_tenant_pk_is_404(client_a, fulfillment_backorder_b):
    assert client_a.get(reverse("procurement:backorder_detail",
                                args=[fulfillment_backorder_b.pk])).status_code == 404


def test_fulfillment_backorder_edit_drops_revised_promise_date(client_a,
                                                               fulfillment_backorder_open_a):
    r = client_a.get(reverse("procurement:backorder_edit",
                             args=[fulfillment_backorder_open_a.pk]))
    assert r.status_code == 200
    assert "procurement/orderfulfillment/backorder/form.html" in _fulfillment_templates(r)
    assert r.context["is_edit"] is True
    assert r.context["obj"].pk == fulfillment_backorder_open_a.pk
    assert "revised_promise_date" not in r.context["form"].fields


def test_fulfillment_backorder_edit_post_updates(client_a, fulfillment_backorder_open_a,
                                                 fulfillment_po_line_a):
    promised = fulfillment_backorder_open_a.revised_promise_date
    body = _fulfillment_backorder_post(po_line=str(fulfillment_po_line_a.pk),
                                       quantity_backordered="5", reason="other",
                                       reason_note="Supplier plant shutdown",
                                       notes="Chased by phone")
    body.pop("revised_promise_date")
    r = client_a.post(reverse("procurement:backorder_edit",
                              args=[fulfillment_backorder_open_a.pk]), body, follow=True)
    assert r.redirect_chain[-1][0] == reverse("procurement:backorder_detail",
                                              args=[fulfillment_backorder_open_a.pk])
    fulfillment_backorder_open_a.refresh_from_db()
    assert fulfillment_backorder_open_a.quantity_backordered == Decimal("5.0000")
    assert fulfillment_backorder_open_a.reason == "other"
    # the promise is untouched by an ordinary edit — only reschedule() may move it
    assert fulfillment_backorder_open_a.revised_promise_date == promised
    assert fulfillment_backorder_open_a.reschedule_count == 0


def test_fulfillment_backorder_edit_refused_once_closed(client_a,
                                                        fulfillment_backorder_closed_a):
    r = client_a.get(reverse("procurement:backorder_edit",
                             args=[fulfillment_backorder_closed_a.pk]), follow=True)
    assert r.redirect_chain[-1][0] == reverse("procurement:backorder_detail",
                                              args=[fulfillment_backorder_closed_a.pk])
    assert any("cannot be edited" in m for m in _fulfillment_messages(r))


def test_fulfillment_backorder_edit_cross_tenant_pk_is_404(client_a, fulfillment_backorder_b):
    assert client_a.get(reverse("procurement:backorder_edit",
                                args=[fulfillment_backorder_b.pk])).status_code == 404


# ------------------------------------------------------------------ backorder delete + verbs


def test_fulfillment_backorder_delete_get_is_405_and_row_survives(client_a,
                                                                  fulfillment_backorder_open_a):
    r = client_a.get(reverse("procurement:backorder_delete",
                             args=[fulfillment_backorder_open_a.pk]))
    assert r.status_code == 405
    assert Backorder.objects.filter(pk=fulfillment_backorder_open_a.pk).exists()


def test_fulfillment_backorder_delete_post_removes_row(client_a, fulfillment_backorder_open_a):
    pk = fulfillment_backorder_open_a.pk
    r = client_a.post(reverse("procurement:backorder_delete", args=[pk]), follow=True)
    assert r.redirect_chain[-1][0] == reverse("procurement:backorder_list")
    assert not Backorder.objects.filter(pk=pk).exists()
    assert _fulfillment_audit(Backorder, fulfillment_backorder_open_a, "delete").exists()


@pytest.mark.parametrize("name", ["backorder_reschedule", "backorder_fulfil", "backorder_cancel",
                                  "backorder_raise_alert"])
def test_fulfillment_backorder_verb_get_is_405(client_a, fulfillment_backorder_open_a, name):
    r = client_a.get(reverse("procurement:%s" % name, args=[fulfillment_backorder_open_a.pk]))
    assert r.status_code == 405
    fulfillment_backorder_open_a.refresh_from_db()
    assert fulfillment_backorder_open_a.status == "open"


@pytest.mark.parametrize("body", [
    {}, {"revised_promise_date": ""}, {"reason_note": "just the note"},
    {"revised_promise_date": "not-a-date", "reason_note": "n"},
])
def test_fulfillment_backorder_reschedule_requires_both_fields(client_a,
                                                               fulfillment_backorder_open_a,
                                                               body):
    r = client_a.post(reverse("procurement:backorder_reschedule",
                              args=[fulfillment_backorder_open_a.pk]), body, follow=True)
    assert any("Give both the new promised date" in m for m in _fulfillment_messages(r))
    fulfillment_backorder_open_a.refresh_from_db()
    assert fulfillment_backorder_open_a.status == "open"
    assert fulfillment_backorder_open_a.reschedule_count == 0


def test_fulfillment_backorder_reschedule_moves_promise_and_counts_the_slip(
        client_a, fulfillment_backorder_open_a):
    was_promised = fulfillment_backorder_open_a.revised_promise_date
    new_date = _fulfillment_today() + _fulfillment_days(12)
    r = client_a.post(reverse("procurement:backorder_reschedule",
                              args=[fulfillment_backorder_open_a.pk]),
                      {"revised_promise_date": new_date.strftime("%Y-%m-%d"),
                       "reason_note": "Plant shutdown extended"}, follow=True)
    assert r.redirect_chain[-1][0] == reverse("procurement:backorder_detail",
                                              args=[fulfillment_backorder_open_a.pk])
    fulfillment_backorder_open_a.refresh_from_db()
    assert fulfillment_backorder_open_a.revised_promise_date == new_date
    assert fulfillment_backorder_open_a.original_promise_date == was_promised
    assert fulfillment_backorder_open_a.status == "rescheduled"
    assert fulfillment_backorder_open_a.reschedule_count == 1
    changes = _fulfillment_audit(Backorder, fulfillment_backorder_open_a, "update").first().changes
    assert changes["action"] == "reschedule" and changes["reschedule_count"] == 1


def test_fulfillment_backorder_reschedule_refused_once_closed(client_a,
                                                              fulfillment_backorder_closed_a):
    r = client_a.post(reverse("procurement:backorder_reschedule",
                              args=[fulfillment_backorder_closed_a.pk]),
                      {"revised_promise_date": _fulfillment_today().strftime("%Y-%m-%d"),
                       "reason_note": "too late"}, follow=True)
    assert any("already closed" in m for m in _fulfillment_messages(r))
    fulfillment_backorder_closed_a.refresh_from_db()
    assert fulfillment_backorder_closed_a.status == "fulfilled"
    assert fulfillment_backorder_closed_a.reschedule_count == 0


def test_fulfillment_backorder_fulfil_closes_on_an_empty_body(client_a,
                                                              fulfillment_backorder_open_a):
    r = client_a.post(reverse("procurement:backorder_fulfil",
                              args=[fulfillment_backorder_open_a.pk]), {}, follow=True)
    assert r.status_code == 200
    fulfillment_backorder_open_a.refresh_from_db()
    assert fulfillment_backorder_open_a.status == "fulfilled"
    assert fulfillment_backorder_open_a.closed_at is not None
    assert fulfillment_backorder_open_a.closure_note == ""


def test_fulfillment_backorder_cancel_records_note_then_noops(client_a,
                                                              fulfillment_backorder_open_a):
    url = reverse("procurement:backorder_cancel", args=[fulfillment_backorder_open_a.pk])
    client_a.post(url, {"closure_note": "Sourced from an alternate supplier"}, follow=True)
    fulfillment_backorder_open_a.refresh_from_db()
    assert fulfillment_backorder_open_a.status == "cancelled"
    assert fulfillment_backorder_open_a.closure_note == "Sourced from an alternate supplier"
    closed_at = fulfillment_backorder_open_a.closed_at

    r = client_a.post(url, {"closure_note": "second try"}, follow=True)
    fulfillment_backorder_open_a.refresh_from_db()
    assert fulfillment_backorder_open_a.closed_at == closed_at
    assert fulfillment_backorder_open_a.closure_note == "Sourced from an alternate supplier"
    assert any("already been closed" in m for m in _fulfillment_messages(r))


def test_fulfillment_backorder_raise_alert_is_idempotent(client_a,
                                                         fulfillment_backorder_past_due_a):
    url = reverse("procurement:backorder_raise_alert",
                  args=[fulfillment_backorder_past_due_a.pk])
    r = client_a.post(url, follow=True)
    assert r.redirect_chain[-1][0] == reverse("procurement:backorder_detail",
                                              args=[fulfillment_backorder_past_due_a.pk])
    fulfillment_backorder_past_due_a.refresh_from_db()
    alert = fulfillment_backorder_past_due_a.alert
    assert alert is not None
    assert alert.kind == "delivery" and alert.severity == "critical"
    assert alert.status == "open"
    assert fulfillment_backorder_past_due_a.number in alert.title
    assert ProcurementAlert.objects.count() == 1
    assert any("Alert raised" in m for m in _fulfillment_messages(r))

    r2 = client_a.post(url, follow=True)
    fulfillment_backorder_past_due_a.refresh_from_db()
    assert fulfillment_backorder_past_due_a.alert_id == alert.pk
    assert ProcurementAlert.objects.count() == 1
    assert any("already has an open alert" in m for m in _fulfillment_messages(r2))


def test_fulfillment_backorder_raise_alert_refused_once_closed(client_a,
                                                               fulfillment_backorder_closed_a):
    r = client_a.post(reverse("procurement:backorder_raise_alert",
                              args=[fulfillment_backorder_closed_a.pk]), follow=True)
    assert any("needs no escalation" in m for m in _fulfillment_messages(r))
    assert ProcurementAlert.objects.count() == 0


# ================================================================== computed boards


def test_fulfillment_inbound_tracking_context_and_stats(client_a, fulfillment_asn_draft_a,
                                                        fulfillment_asn_in_transit_a,
                                                        fulfillment_asn_late_a,
                                                        fulfillment_asn_delivered_a,
                                                        fulfillment_carrier_a):
    r = client_a.get(reverse("procurement:inbound_tracking"))
    assert r.status_code == 200
    assert "procurement/orderfulfillment/inbound_tracking.html" in _fulfillment_templates(r)

    ctx = r.context
    # hard-limited to the in-flight statuses, soonest expected arrival first
    assert _fulfillment_pks(r) == [fulfillment_asn_late_a.pk, fulfillment_asn_in_transit_a.pk]
    assert ctx["page_obj"].paginator.count == 2
    assert ctx["q"] == ""
    assert [v for v, _ in ctx["status_choices"]] == ["submitted", "in_transit"]
    assert [c.pk for c in ctx["carriers"]] == [fulfillment_carrier_a.pk]
    assert ctx["stats"] == {"in_flight": 2, "late": 1, "unlinked": 2, "arriving_today": 0}
    assert fulfillment_asn_late_a.number in r.content.decode()


def test_fulfillment_inbound_tracking_reads_the_linked_shipment_projection(
        client_a, fulfillment_asn_in_transit_a, fulfillment_shipment_inbound_a):
    AdvancedShipmentNotice.objects.filter(pk=fulfillment_asn_in_transit_a.pk).update(
        shipment=fulfillment_shipment_inbound_a)
    r = client_a.get(reverse("procurement:inbound_tracking"))
    body = r.content.decode()
    assert "Rotterdam hub" in body
    assert "In Transit" in body
    assert r.context["stats"]["unlinked"] == 0


def test_fulfillment_inbound_tracking_search_filters_and_late(client_a,
                                                              fulfillment_asn_in_transit_a,
                                                              fulfillment_asn_late_a,
                                                              fulfillment_carrier_a):
    url = reverse("procurement:inbound_tracking")

    r = client_a.get(url, {"q": "NW-DN-2003"})
    assert _fulfillment_pks(r) == [fulfillment_asn_late_a.pk]

    r = client_a.get(url, {"late": "1"})
    assert _fulfillment_pks(r) == [fulfillment_asn_late_a.pk]
    assert r.context["page_obj"].paginator.count == 1

    r = client_a.get(url, {"status": "in_transit"})
    assert len(_fulfillment_pks(r)) == 2

    AdvancedShipmentNotice.objects.filter(pk=fulfillment_asn_late_a.pk).update(
        carrier=fulfillment_carrier_a)
    r = client_a.get(url, {"carrier": str(fulfillment_carrier_a.pk)})
    assert _fulfillment_pks(r) == [fulfillment_asn_late_a.pk]


@pytest.mark.parametrize("params", [
    {"carrier": "abc"}, {"carrier": "99999999999999999999"}, {"status": "zzz"},
    {"page": "abc"}, {"page": "999"},
])
def test_fulfillment_inbound_tracking_junk_params_never_500(client_a,
                                                            fulfillment_asn_in_transit_a,
                                                            params):
    r = client_a.get(reverse("procurement:inbound_tracking"), params)
    assert r.status_code == 200 and "object_list" in r.context


def test_fulfillment_inbound_tracking_pagination_page_two(client_a, tenant_a, fulfillment_po_a):
    _fulfillment_bulk_asns(tenant_a, fulfillment_po_a, 17, status="in_transit")
    url = reverse("procurement:inbound_tracking")

    first = client_a.get(url)
    assert len(first.context["object_list"]) == 15
    assert first.context["page_obj"].paginator.num_pages == 2

    second = client_a.get(url, {"page": "2"})
    assert len(second.context["object_list"]) == 2
    assert second.context["page_obj"].number == 2
    assert set(_fulfillment_pks(first)).isdisjoint(_fulfillment_pks(second))


def test_fulfillment_inbound_tracking_query_count_is_bounded(client_a, tenant_a,
                                                             fulfillment_po_a,
                                                             fulfillment_carrier_a,
                                                             django_assert_max_num_queries):
    rows = _fulfillment_bulk_asns(tenant_a, fulfillment_po_a, 15, status="in_transit")
    # Carrier.name is a property off party.name — the board select_relates carrier__party
    # exactly so this stays flat.
    AdvancedShipmentNotice.objects.filter(pk__in=[r.pk for r in rows]).update(
        carrier=fulfillment_carrier_a)
    with django_assert_max_num_queries(14):
        r = client_a.get(reverse("procurement:inbound_tracking"))
        assert r.status_code == 200
        assert len(r.context["object_list"]) == 15
        r.content.decode()


def test_fulfillment_inbound_tracking_is_tenant_scoped(client_a, fulfillment_asn_late_a,
                                                       fulfillment_asn_b):
    AdvancedShipmentNotice.objects.filter(pk=fulfillment_asn_b.pk).update(status="in_transit")
    r = client_a.get(reverse("procurement:inbound_tracking"))
    assert _fulfillment_pks(r) == [fulfillment_asn_late_a.pk]


# ------------------------------------------------------------------ delivery confirmation


def test_fulfillment_delivery_confirmation_default_bucket_and_stats(
        client_a, tenant_a, fulfillment_po_a, fulfillment_asn_in_transit_a,
        fulfillment_asn_late_a, fulfillment_asn_delivered_a):
    due_today = AdvancedShipmentNotice.objects.create(
        tenant=tenant_a, purchase_order=fulfillment_po_a, status="in_transit",
        supplier_reference="NW-DN-TODAY", expected_delivery_date=_fulfillment_today())

    r = client_a.get(reverse("procurement:delivery_confirmation"))
    assert r.status_code == 200
    assert ("procurement/orderfulfillment/delivery_confirmation.html"
            in _fulfillment_templates(r))
    ctx = r.context
    assert ctx["bucket"] == "today"
    assert [v for v, _ in ctx["bucket_choices"]] == ["today", "overdue", "awaiting", "confirmed"]
    assert [v for v, _ in ctx["condition_choices"]] == ["good", "damaged", "partial", "refused"]
    assert ctx["q"] == ""
    assert _fulfillment_pks(r) == [due_today.pk]
    assert ctx["page_obj"].paginator.count == 1
    assert ctx["stats"] == {"due_today": 1, "overdue": 1, "awaiting": 1, "confirmed_7d": 1}
    assert due_today.number in r.content.decode()


@pytest.mark.parametrize("bucket,fixture_name", [
    ("overdue", "fulfillment_asn_late_a"),
    ("awaiting", "fulfillment_asn_in_transit_a"),
    ("confirmed", "fulfillment_asn_delivered_a"),
])
def test_fulfillment_delivery_confirmation_bucket_tabs(client_a, request, bucket, fixture_name):
    request.getfixturevalue("fulfillment_asn_in_transit_a")
    request.getfixturevalue("fulfillment_asn_late_a")
    request.getfixturevalue("fulfillment_asn_delivered_a")
    expected = request.getfixturevalue(fixture_name)

    r = client_a.get(reverse("procurement:delivery_confirmation"), {"due": bucket})
    assert r.status_code == 200
    assert r.context["bucket"] == bucket
    assert _fulfillment_pks(r) == [expected.pk]


def test_fulfillment_delivery_confirmation_awaiting_includes_undated(client_a, tenant_a,
                                                                     fulfillment_po_a,
                                                                     fulfillment_asn_in_transit_a):
    undated = AdvancedShipmentNotice.objects.create(
        tenant=tenant_a, purchase_order=fulfillment_po_a, status="submitted",
        supplier_reference="NW-DN-UNDATED", expected_delivery_date=None)
    r = client_a.get(reverse("procurement:delivery_confirmation"), {"due": "awaiting"})
    assert set(_fulfillment_pks(r)) == {undated.pk, fulfillment_asn_in_transit_a.pk}
    assert r.context["stats"]["awaiting"] == 2


@pytest.mark.parametrize("raw", ["zzz", "", "1", "TODAY", "../../etc"])
def test_fulfillment_delivery_confirmation_unknown_bucket_falls_back(client_a,
                                                                     fulfillment_asn_late_a,
                                                                     raw):
    r = client_a.get(reverse("procurement:delivery_confirmation"), {"due": raw})
    assert r.status_code == 200
    assert r.context["bucket"] == "today"


def test_fulfillment_delivery_confirmation_search_narrows(client_a, tenant_a, fulfillment_po_a):
    rows = _fulfillment_bulk_asns(tenant_a, fulfillment_po_a, 3, status="in_transit",
                                  expected=_fulfillment_today())
    r = client_a.get(reverse("procurement:delivery_confirmation"), {"q": "BULK-001"})
    assert _fulfillment_pks(r) == [rows[1].pk]
    assert r.context["q"] == "BULK-001"


def test_fulfillment_delivery_confirmation_pagination_and_query_count(
        client_a, tenant_a, fulfillment_po_a, fulfillment_carrier_a,
        django_assert_max_num_queries):
    rows = _fulfillment_bulk_asns(tenant_a, fulfillment_po_a, 17, status="in_transit",
                                  expected=_fulfillment_today())
    AdvancedShipmentNotice.objects.filter(pk__in=[r.pk for r in rows]).update(
        carrier=fulfillment_carrier_a)
    url = reverse("procurement:delivery_confirmation")

    with django_assert_max_num_queries(14):
        first = client_a.get(url)
        assert len(first.context["object_list"]) == 15
        first.content.decode()

    second = client_a.get(url, {"page": "2"})
    assert len(second.context["object_list"]) == 2
    assert second.context["page_obj"].number == 2

    past = client_a.get(url, {"page": "900"})
    assert past.status_code == 200 and past.context["page_obj"].number == 2


def test_fulfillment_delivery_confirmation_is_tenant_scoped(client_a, tenant_b,
                                                            fulfillment_po_b,
                                                            fulfillment_asn_late_a):
    AdvancedShipmentNotice.objects.create(
        tenant=tenant_b, purchase_order=fulfillment_po_b, status="in_transit",
        supplier_reference="GBX-DN-TODAY", expected_delivery_date=_fulfillment_today())
    r = client_a.get(reverse("procurement:delivery_confirmation"), {"due": "overdue"})
    assert _fulfillment_pks(r) == [fulfillment_asn_late_a.pk]
    assert r.context["stats"]["due_today"] == 0
