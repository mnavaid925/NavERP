"""Inventory 5.15 — Quality Control & Inspection views.

The four QC registers (checklists, routing rules, quarantine orders, defect reports):
list rendering under every filter permutation, detail context (obj/moves/is_admin),
the create/edit privilege split, the quarantine lifecycle walked through HTTP as
client_a (real ledger pairs plus view-level double-click safety), crafted-POST edit and
delete guards on rows whose number is already provenance in the ledger, the routing
rule's live resolution preview matrix, checklist create with its inline checkpoint
formset (parent + children in one atomic block), and seed_inventory's QC idempotence.
"""
from decimal import Decimal

import pytest
from django.core.management import call_command
from django.db.models import Sum
from django.urls import reverse

from apps.inventory.forms import QcChecklistItemFormSet
from apps.inventory.models import (
    DefectReport,
    QcChecklist,
    QcChecklistItem,
    QcRoutingRule,
    QuarantineOrder,
)
from apps.scm.models import StockMove

pytestmark = pytest.mark.django_db


# -- helpers ------------------------------------------------------------------------------------

def _checklist_row(label, kind="visual", sequence=10, mandatory=True):
    """One inline checkpoint row as the formset binds it."""
    return {"label": label, "kind": kind, "expected_result": "",
            "is_mandatory": "on" if mandatory else "", "sequence": str(sequence)}


def _formset_payload(rows):
    """A management form + child rows for QcChecklistItemFormSet's default prefix."""
    prefix = QcChecklistItemFormSet.get_default_prefix()
    data = {f"{prefix}-TOTAL_FORMS": str(len(rows)),
            f"{prefix}-INITIAL_FORMS": "0",
            f"{prefix}-MIN_NUM_FORMS": "0",
            f"{prefix}-MAX_NUM_FORMS": "1000"}
    for i, row in enumerate(rows):
        for field, value in row.items():
            data[f"{prefix}-{i}-{field}"] = value
    return data


def _quarantine_edit_payload(order):
    """A fully valid QuarantineOrderForm body carrying the crafted quantity 99."""
    return {"item": order.item_id, "lot_serial": "",
            "source_location": order.source_location_id,
            "quarantine_location": order.quarantine_location_id,
            "quantity": "99", "reason": order.reason,
            "reference": "HACKED", "notes": "crafted POST"}


# -- Lists --------------------------------------------------------------------------------------

def test_qc_lists_render_for_all_four_entities(client_a, qc_checklist_a, qc_rule_catchall_a,
                                               qrd_draft_a, defect_open_a):
    cases = [
        ("qcchecklist_list", b"QC Checklists", qc_checklist_a),
        ("qcroutingrule_list", b"Inspection Routing Rules", qc_rule_catchall_a),
        ("quarantineorder_list", b"Quarantine Orders", qrd_draft_a),
        ("defectreport_list", b"Defect Reports", defect_open_a),
    ]
    for name, marker, obj in cases:
        response = client_a.get(reverse(f"inventory:{name}"))
        assert response.status_code == 200, name
        assert marker in response.content
        assert obj in response.context["object_list"], name


def test_qcchecklist_list_filters_narrow_and_junk_degrades(
        client_a, tenant_a, item_a, vendor_party_a, qc_checklist_a):
    item_pinned = QcChecklist.objects.create(
        tenant=tenant_a, name="Item pinned check", item=item_a)
    vendor_pinned = QcChecklist.objects.create(
        tenant=tenant_a, name="Vendor pinned check", vendor=vendor_party_a)
    retired = QcChecklist.objects.create(
        tenant=tenant_a, name="Retired dock check", is_active=False)
    base = reverse("inventory:qcchecklist_list")

    hit = client_a.get(base + "?is_active=active")
    assert hit.status_code == 200
    assert {row.pk for row in hit.context["object_list"]} == {
        qc_checklist_a.pk, item_pinned.pk, vendor_pinned.pk}
    hit = client_a.get(base + "?is_active=inactive")
    assert {row.pk for row in hit.context["object_list"]} == {retired.pk}
    hit = client_a.get(base + "?scope=item")
    assert {row.pk for row in hit.context["object_list"]} == {item_pinned.pk}
    hit = client_a.get(base + "?scope=vendor")
    assert {row.pk for row in hit.context["object_list"]} == {vendor_pinned.pk}
    hit = client_a.get(base + "?scope=workspace")
    assert {row.pk for row in hit.context["object_list"]} == {qc_checklist_a.pk, retired.pk}

    junk = client_a.get(base + "?is_active=bogus&scope=bogus&page=99")
    assert junk.status_code == 200
    assert len(junk.context["object_list"]) == 4

    miss = client_a.get(base + "?q=nothing-matches-this")
    assert miss.status_code == 200
    assert len(miss.context["object_list"]) == 0


def test_qcroutingrule_list_filters_narrow_and_search_miss_empties(
        client_a, tenant_a, qc_zone_a, qc_rule_item_a, qc_rule_catchall_a):
    bypass = QcRoutingRule.objects.create(
        tenant=tenant_a, name="Trusted category bypass", verdict="bypass", priority=20)
    retired = QcRoutingRule.objects.create(
        tenant=tenant_a, name="Retired gate", verdict="inspect",
        qc_location=qc_zone_a, is_active=False)
    base = reverse("inventory:qcroutingrule_list")

    hit = client_a.get(base + "?verdict=inspect")
    assert hit.status_code == 200
    assert {row.pk for row in hit.context["object_list"]} == {
        qc_rule_item_a.pk, qc_rule_catchall_a.pk, retired.pk}
    hit = client_a.get(base + "?verdict=bypass")
    assert {row.pk for row in hit.context["object_list"]} == {bypass.pk}
    hit = client_a.get(base + "?is_active=active")
    assert {row.pk for row in hit.context["object_list"]} == {
        qc_rule_item_a.pk, qc_rule_catchall_a.pk, bypass.pk}
    hit = client_a.get(base + "?is_active=inactive")
    assert {row.pk for row in hit.context["object_list"]} == {retired.pk}

    junk = client_a.get(base + "?verdict=bogus&is_active=maybe&page=99")
    assert junk.status_code == 200
    assert len(junk.context["object_list"]) == 4

    miss = client_a.get(base + "?q=nothing-matches-this")
    assert miss.status_code == 200
    assert len(miss.context["object_list"]) == 0


def test_quarantineorder_list_status_filter_narrows_and_miss_empties(
        client_a, tenant_a, item_a, qc_warehouse_a, qc_zone_a, qrd_quarantined_a):
    # qrd_draft_a and qrd_quarantined_a are the SAME row (the latter fixture walks it
    # through quarantine()), so this test mints its own still-draft order to filter on.
    draft = QuarantineOrder.objects.create(
        tenant=tenant_a, item=item_a, source_location=qc_warehouse_a,
        quarantine_location=qc_zone_a, quantity=Decimal("1"), reason="damage_found")
    base = reverse("inventory:quarantineorder_list")

    hit = client_a.get(base + "?status=draft")
    assert hit.status_code == 200
    assert {row.pk for row in hit.context["object_list"]} == {draft.pk}
    hit = client_a.get(base + "?status=quarantined")
    assert {row.pk for row in hit.context["object_list"]} == {qrd_quarantined_a.pk}
    hit = client_a.get(base + "?status=released")
    assert hit.status_code == 200
    assert len(hit.context["object_list"]) == 0

    junk = client_a.get(base + "?status=bogus&page=99")
    assert junk.status_code == 200

    miss = client_a.get(base + "?q=nothing-matches-this")
    assert miss.status_code == 200
    assert len(miss.context["object_list"]) == 0


def test_defectreport_list_filters_narrow_and_miss_empties(
        client_a, tenant_a, item_a, qc_warehouse_a, defect_open_a):
    minor = DefectReport.objects.create(
        tenant=tenant_a, item=item_a, location=qc_warehouse_a,
        quantity=Decimal("1"), defect_type="visual_cosmetic", severity="minor")
    base = reverse("inventory:defectreport_list")

    hit = client_a.get(base + "?status=open")
    assert hit.status_code == 200
    assert {row.pk for row in hit.context["object_list"]} == {defect_open_a.pk, minor.pk}
    hit = client_a.get(base + "?severity=major")
    assert {row.pk for row in hit.context["object_list"]} == {defect_open_a.pk}
    hit = client_a.get(base + "?severity=minor")
    assert {row.pk for row in hit.context["object_list"]} == {minor.pk}
    hit = client_a.get(base + "?severity=critical")
    assert hit.status_code == 200
    assert len(hit.context["object_list"]) == 0

    junk = client_a.get(base + "?status=bogus&severity=bogus&page=99")
    assert junk.status_code == 200

    miss = client_a.get(base + "?q=nothing-matches-this")
    assert miss.status_code == 200
    assert len(miss.context["object_list"]) == 0


# -- Details ------------------------------------------------------------------------------------

def test_quarantine_detail_exposes_obj_moves_is_admin(client_a, qrd_quarantined_a):
    response = client_a.get(
        reverse("inventory:quarantineorder_detail", args=[qrd_quarantined_a.pk]))
    assert response.status_code == 200
    assert response.context["obj"] == qrd_quarantined_a
    assert response.context["is_admin"] is True
    expected = set(qrd_quarantined_a.ledger_moves().values_list("pk", flat=True))
    assert {move.pk for move in response.context["moves"]} == expected
    assert qrd_quarantined_a.number.encode() in response.content


def test_defect_detail_exposes_obj_moves_is_admin(client_a, defect_written_off_a):
    response = client_a.get(
        reverse("inventory:defectreport_detail", args=[defect_written_off_a.pk]))
    assert response.status_code == 200
    assert response.context["obj"] == defect_written_off_a
    assert response.context["is_admin"] is True
    legs = StockMove.objects.filter(
        tenant_id=defect_written_off_a.tenant_id, reference=defect_written_off_a.number)
    assert {move.pk for move in response.context["moves"]} == set(legs.values_list("pk", flat=True))
    assert defect_written_off_a.number.encode() in response.content


def test_checklist_detail_renders_checkpoints_in_sequence_order(client_a, tenant_a):
    checklist = QcChecklist.objects.create(tenant=tenant_a, name="Ordered gate")
    for seq, label in [(30, "Third"), (10, "First"), (20, "Second")]:
        QcChecklistItem.objects.create(
            tenant=tenant_a, checklist=checklist, label=label, kind="visual",
            sequence=seq)

    response = client_a.get(reverse("inventory:qcchecklist_detail", args=[checklist.pk]))
    assert response.status_code == 200
    items = list(response.context["items"])
    assert [item.sequence for item in items] == [10, 20, 30]
    assert [item.label for item in items] == ["First", "Second", "Third"]
    assert response.context["obj"] == checklist
    assert response.context["is_admin"] is True


# -- Create / edit pages ------------------------------------------------------------------------

def test_qc_create_pages_render_for_admin_with_form(client_a, qc_zone_a):
    for name in ("qcchecklist_create", "qcroutingrule_create",
                 "quarantineorder_create", "defectreport_create"):
        response = client_a.get(reverse(f"inventory:{name}"))
        assert response.status_code == 200, name
        assert "form" in response.context, name


def test_qc_edit_pages_render_for_admin_prefilled(client_a, qc_checklist_a,
                                                  qc_rule_item_a, qrd_draft_a,
                                                  defect_open_a):
    cases = [("qcchecklist_edit", qc_checklist_a),
             ("qcroutingrule_edit", qc_rule_item_a),
             ("quarantineorder_edit", qrd_draft_a),
             ("defectreport_edit", defect_open_a)]
    for name, obj in cases:
        response = client_a.get(reverse(f"inventory:{name}", args=[obj.pk]))
        assert response.status_code == 200, name
        assert response.context["form"].instance == obj, name


def test_member_gets_403_on_config_master_pages(member_client, qc_checklist_a,
                                                qc_rule_item_a):
    cases = [("qcchecklist_create", None), ("qcchecklist_edit", qc_checklist_a),
             ("qcroutingrule_create", None), ("qcroutingrule_edit", qc_rule_item_a)]
    for name, obj in cases:
        url = (reverse(f"inventory:{name}") if obj is None
               else reverse(f"inventory:{name}", args=[obj.pk]))
        assert member_client.get(url).status_code == 403, name


def test_member_operator_pages_render(member_client, qrd_draft_a, defect_open_a):
    assert member_client.get(reverse("inventory:quarantineorder_create")).status_code == 200
    assert member_client.get(reverse(
        "inventory:quarantineorder_edit", args=[qrd_draft_a.pk])).status_code == 200
    assert member_client.get(reverse(
        "inventory:defectreport_edit", args=[defect_open_a.pk])).status_code == 200


# -- Quarantine lifecycle over HTTP ---------------------------------------------------------------

class TestQuarantineLifecycleOverHTTP:
    """The POST-only verbs as client_a: real ledger pairs and flash refusals."""

    def test_quarantine_on_draft_posts_pair_and_flips_status(
            self, client_a, qrd_draft_a, qc_stocked_a):
        url = reverse("inventory:quarantineorder_quarantine", args=[qrd_draft_a.pk])
        response = client_a.post(url)
        assert response.status_code == 302
        assert response.url == reverse(
            "inventory:quarantineorder_detail", args=[qrd_draft_a.pk])
        qrd_draft_a.refresh_from_db()
        assert qrd_draft_a.status == "quarantined"

        legs = StockMove.objects.filter(
            tenant_id=qrd_draft_a.tenant_id, reference=qrd_draft_a.number)
        assert legs.count() == 2
        assert set(legs.values_list("move_type", flat=True)) == {"transfer"}
        assert set(legs.values_list("location_id", flat=True)) == {
            qrd_draft_a.source_location_id, qrd_draft_a.quarantine_location_id}
        assert legs.aggregate(net=Sum("quantity"))["net"] == Decimal("0")

        followed = client_a.get(response.url)
        assert b"moved into quarantine." in followed.content

    def test_release_returns_goods_and_flips_status(self, client_a, qrd_draft_a,
                                                    qc_stocked_a):
        client_a.post(reverse(
            "inventory:quarantineorder_quarantine", args=[qrd_draft_a.pk]))
        response = client_a.post(reverse(
            "inventory:quarantineorder_release", args=[qrd_draft_a.pk]))
        assert response.status_code == 302
        qrd_draft_a.refresh_from_db()
        assert qrd_draft_a.status == "released"

        legs = StockMove.objects.filter(
            tenant_id=qrd_draft_a.tenant_id, reference=qrd_draft_a.number)
        assert legs.count() == 4
        assert legs.aggregate(net=Sum("quantity"))["net"] == Decimal("0")
        source_total = StockMove.objects.filter(
            tenant_id=qrd_draft_a.tenant_id, item_id=qrd_draft_a.item_id,
            location_id=qrd_draft_a.source_location_id).aggregate(q=Sum("quantity"))["q"]
        assert source_total == Decimal("10.0000")   # qc_stocked_a's opening receipt intact

        followed = client_a.get(response.url)
        assert b"released back to stock." in followed.content

    def test_second_quarantine_after_release_is_flash_refused(
            self, client_a, qrd_draft_a, qc_stocked_a):
        client_a.post(reverse(
            "inventory:quarantineorder_quarantine", args=[qrd_draft_a.pk]))
        client_a.post(reverse(
            "inventory:quarantineorder_release", args=[qrd_draft_a.pk]))
        legs_before = StockMove.objects.filter(reference=qrd_draft_a.number).count()

        response = client_a.post(reverse(
            "inventory:quarantineorder_quarantine", args=[qrd_draft_a.pk]))
        assert response.status_code == 302
        assert response.url == reverse(
            "inventory:quarantineorder_detail", args=[qrd_draft_a.pk])

        qrd_draft_a.refresh_from_db()
        assert qrd_draft_a.status == "released"
        assert StockMove.objects.filter(
            reference=qrd_draft_a.number).count() == legs_before
        followed = client_a.get(response.url)
        assert b"cannot be quarantined" in followed.content


# -- Crafted-POST guards ------------------------------------------------------------------------

def test_crafted_edit_on_quarantined_order_changes_nothing(client_a, qrd_quarantined_a,
                                                           qc_stocked_a):
    edit_url = reverse("inventory:quarantineorder_edit", args=[qrd_quarantined_a.pk])
    response = client_a.post(edit_url, data=_quarantine_edit_payload(qrd_quarantined_a))
    assert response.status_code == 302
    assert response.url == reverse(
        "inventory:quarantineorder_detail", args=[qrd_quarantined_a.pk])

    followed = client_a.get(response.url)
    assert b"can no longer be edited" in followed.content

    qrd_quarantined_a.refresh_from_db()
    assert qrd_quarantined_a.quantity == Decimal("2.0000")
    assert qrd_quarantined_a.reference == ""
    assert qrd_quarantined_a.notes == ""
    assert qrd_quarantined_a.status == "quarantined"
    assert qrd_quarantined_a.ledger_moves().count() == 2


# -- Delete guards --------------------------------------------------------------------------------

def test_delete_post_on_quarantined_order_is_refused_row_alive(
        client_a, qrd_quarantined_a, qc_stocked_a):
    response = client_a.post(reverse(
        "inventory:quarantineorder_delete", args=[qrd_quarantined_a.pk]))
    assert response.status_code == 302
    assert QuarantineOrder.objects.filter(pk=qrd_quarantined_a.pk).exists()
    assert b"cannot be deleted" in client_a.get(response.url).content


def test_delete_post_on_written_off_defect_is_refused_row_alive(
        client_a, defect_written_off_a):
    response = client_a.post(reverse(
        "inventory:defectreport_delete", args=[defect_written_off_a.pk]))
    assert response.status_code == 302
    assert DefectReport.objects.filter(pk=defect_written_off_a.pk).exists()
    assert b"cannot be deleted" in client_a.get(response.url).content


def test_delete_own_draft_quarantine_removes_row(client_a, qrd_draft_a):
    response = client_a.post(reverse(
        "inventory:quarantineorder_delete", args=[qrd_draft_a.pk]))
    assert response.status_code == 302
    assert response.url == reverse("inventory:quarantineorder_list")
    assert not QuarantineOrder.objects.filter(pk=qrd_draft_a.pk).exists()


def test_delete_own_open_defect_removes_row(client_a, defect_open_a):
    response = client_a.post(reverse(
        "inventory:defectreport_delete", args=[defect_open_a.pk]))
    assert response.status_code == 302
    assert not DefectReport.objects.filter(pk=defect_open_a.pk).exists()


# -- Routing-rule live preview ----------------------------------------------------------------------

def test_routing_preview_without_item_renders_empty_picker(client_a, qc_rule_item_a):
    response = client_a.get(
        reverse("inventory:qcroutingrule_detail", args=[qc_rule_item_a.pk]))
    assert response.status_code == 200
    assert response.context["preview"] is None
    assert b"Pick an item" in response.content


def test_routing_preview_known_item_reports_reason_and_winner(client_a, qc_rule_item_a,
                                                              item_a):
    url = (reverse("inventory:qcroutingrule_detail", args=[qc_rule_item_a.pk])
           + f"?item={item_a.pk}")
    response = client_a.get(url)
    assert response.status_code == 200
    preview = response.context["preview"]
    assert preview is not None
    assert preview["verdict"] == "inspect"
    assert preview["reason"].startswith("Matched item rule")
    assert "Item-tier inspect" in preview["reason"]
    assert preview["is_this_rule"] is True
    assert b"Matched item rule" in response.content


def test_routing_preview_unknown_item_pk_renders_without_preview(client_a, qc_rule_item_a):
    url = (reverse("inventory:qcroutingrule_detail", args=[qc_rule_item_a.pk])
           + "?item=999999")
    response = client_a.get(url)
    assert response.status_code == 200
    assert response.context["preview"] is None


def test_routing_preview_garbage_and_overrange_item_pk_render(client_a, qc_rule_item_a):
    base = reverse("inventory:qcroutingrule_detail", args=[qc_rule_item_a.pk])
    garbage = client_a.get(base + "?item=garbage")
    assert garbage.status_code == 200
    assert garbage.context["preview"] is None
    overrange = client_a.get(base + "?item=999999999999999999999999")
    assert overrange.status_code == 200
    assert overrange.context["preview"] is None


# -- Checklist create with its checkpoint formset -----------------------------------------------------

def test_checklist_create_saves_parent_and_two_checkpoints_atomically(client_a, tenant_a):
    payload = {"name": "Gate Check B", "item": "", "vendor": "",
               "description": "Two-step probe", "is_active": "on"}
    payload.update(_formset_payload([
        _checklist_row("Seal intact", kind="visual", sequence=5),
        _checklist_row("Count matches", kind="quantity", sequence=15),
    ]))

    response = client_a.post(reverse("inventory:qcchecklist_create"), data=payload)
    created = QcChecklist.objects.get(tenant=tenant_a, name="Gate Check B")
    assert response.status_code == 302
    assert response.url == reverse("inventory:qcchecklist_detail", args=[created.pk])

    rows = list(created.checklist_items.order_by("sequence"))
    assert [row.sequence for row in rows] == [5, 15]
    assert [row.label for row in rows] == ["Seal intact", "Count matches"]
    assert [row.kind for row in rows] == ["visual", "quantity"]
    assert all(row.tenant_id == tenant_a.pk for row in rows)


def test_checklist_create_foreign_vendor_rolls_back_parent_and_children(
        client_a, vendor_party_b):
    checklists_before = QcChecklist.objects.count()
    items_before = QcChecklistItem.objects.count()

    payload = {"name": "Foreign vendor probe", "item": "", "vendor": vendor_party_b.pk,
               "description": "", "is_active": "on"}
    payload.update(_formset_payload([
        _checklist_row("Row one"), _checklist_row("Row two", sequence=20),
    ]))
    response = client_a.post(reverse("inventory:qcchecklist_create"), data=payload)

    assert response.status_code == 200
    assert "vendor" in response.context["form"].errors
    assert QcChecklist.objects.count() == checklists_before
    assert QcChecklistItem.objects.count() == items_before


# -- Seeder idempotence -----------------------------------------------------------------------------

def test_seed_inventory_qc_rows_survive_a_second_run(db, tenant_a, item_a):
    """seed_inventory twice: the QC pass skips a tenant that already holds its rows,
    so every QC table's count is stable across runs."""
    from io import StringIO

    from apps.inventory.models import BarcodeLabel

    # A label already on the books sends the 5.14 pass down its idempotent skip
    # branch; see the reported NameError in _seed_barcode_labels_and_scans.
    BarcodeLabel.objects.create(tenant=tenant_a, target_type="item", item=item_a,
                                label_kind="product", symbology="code128", copies=1)

    models = (QcChecklistItem, QcChecklist, QcRoutingRule, QuarantineOrder, DefectReport)

    call_command("seed_inventory", stdout=StringIO(), stderr=StringIO())
    first = {model.__name__: model.objects.filter(tenant=tenant_a).count()
             for model in models}

    call_command("seed_inventory", stdout=StringIO(), stderr=StringIO())
    second = {model.__name__: model.objects.filter(tenant=tenant_a).count()
              for model in models}

    assert first == second
    assert first["QcChecklist"] >= 1
    assert first["QcRoutingRule"] >= 1
