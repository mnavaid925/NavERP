"""Inventory 5.11 Stocktaking & Cycle Counting — views.

The HTTP surface over the two documents and the one computed page: CountProgram CRUD +
its ``run`` verb (mints/reuses SCM's spine sheet and stamps ``last_run_date``, refuses
an inactive cadence with a flash), PhysicalInventory CRUD + the three lifecycle verbs
(start / reconcile / cancel — every refusal is POST-only flash traffic on the detail
page), and the variance lens deriving its row dicts from counted sheets only. Deletes
are drafts-only, every foreign-workspace route 404s, and both lists search + paginate.

Login/client pattern mirrors test_tracking_views.py: root-conftest ``client_a`` /
``client_b`` force-login the tenant admins; 5.11 fixtures come from tests/conftest.py.
"""
from decimal import Decimal

import pytest
from django.urls import reverse
from django.utils import timezone

from apps.inventory.models import CountProgram, PhysicalInventory
from apps.scm.models import CycleCountTask

pytestmark = pytest.mark.django_db


# ------------------------------------------------------------------ helpers


def _stocktake_program(tenant, *, name="Probe cadence", location=None, **fields):
    """A CountProgram row straight through the ORM (create() skips full_clean)."""
    fields.setdefault("frequency", "daily")
    return CountProgram.objects.create(
        tenant=tenant, name=name, location=location,
        count_method=fields.pop("count_method", "zone"), **fields)


def _stocktake_event_payload(warehouse, **overrides):
    """A valid PhysicalInventoryForm submission."""
    data = {"warehouse": warehouse.pk, "scheduled_date": "2026-08-24",
            "notes": "Raised over HTTP"}
    data.update(overrides)
    return data


def _stocktake_sheet(tenant, location, *, status="scheduled", scheduled_date=None,
                     count_method="full", notes=""):
    """A spine CycleCountTask as the 5.11 pages see it (conftest's pinned shape).

    Statuses are ordinary spine data, so tests flip spawned sheets by writing rows.
    """
    from apps.scm.models import CycleCountTask

    return CycleCountTask.objects.create(
        tenant=tenant, location=location,
        scheduled_date=scheduled_date or timezone.localdate(),
        count_method=count_method, status=status, notes=notes)


def _stocktake_line(task, item, *, expected="10", counted=None):
    """One blind-count line: expected snapshotted server-side, counted None until counted."""
    from apps.scm.models import CycleCountTaskLine

    return CycleCountTaskLine.objects.create(
        cycle_count=task, item=item, expected_quantity=Decimal(expected),
        counted_quantity=None if counted is None else Decimal(counted))


def _stocktake_flashes(response):
    return [str(message) for message in response.context["messages"]]


# ------------------------------------------------------------------ countprogram list


def test_stocktake_program_list_renders_row_with_context_contract(
        client_a, tenant_a, stocktake_program_a):
    response = client_a.get(reverse("inventory:countprogram_list"))
    assert response.status_code == 200
    assert stocktake_program_a.name.encode() in response.content
    assert stocktake_program_a in list(response.context["object_list"])
    assert "page_obj" in response.context and "q" in response.context
    assert "frequency_choices" in response.context
    assert "today" in response.context
    expected_due = sum(1 for p in CountProgram.objects.filter(tenant=tenant_a)
                       if p.is_due(timezone.localdate()))
    assert response.context["due_count"] == expected_due


def test_stocktake_program_list_search_hit_by_name_and_location_miss(
        client_a, stocktake_program_a, stocktake_zone_a):
    url = reverse("inventory:countprogram_list")
    hit = client_a.get(url + "?q=zone+sweep")
    assert hit.status_code == 200
    assert [obj.pk for obj in hit.context["object_list"]] == [stocktake_program_a.pk]

    hit = client_a.get(url + f"?q={stocktake_zone_a.code}")
    assert [obj.pk for obj in hit.context["object_list"]] == [stocktake_program_a.pk]

    miss = client_a.get(url + "?q=zzz-nothing")
    assert miss.status_code == 200
    assert list(miss.context["object_list"]) == []


def test_stocktake_program_list_pagination_two_pages(
        client_a, tenant_a):
    for i in range(1, 17):
        _stocktake_program(tenant_a, name=f"Bulk cadence {i:02d}")

    page_one = client_a.get(reverse("inventory:countprogram_list"))
    assert page_one.status_code == 200
    assert page_one.context["page_obj"].number == 1
    assert page_one.context["page_obj"].paginator.num_pages == 2
    assert len(page_one.context["object_list"]) == 15

    page_two = client_a.get(reverse("inventory:countprogram_list") + "?page=2")
    assert page_two.status_code == 200
    assert page_two.context["page_obj"].number == 2
    assert len(page_two.context["object_list"]) == 1


# ------------------------------------------------------------------ countprogram CRUD


def test_stocktake_program_create_get_renders_blank_form(client_a):
    response = client_a.get(reverse("inventory:countprogram_create"))
    assert response.status_code == 200
    assert response.context["form"] is not None
    assert response.context["is_edit"] is False


def test_stocktake_program_create_post_valid_redirects_to_list_and_row_exists(
        client_a, tenant_a, admin_user, stocktake_zone_a):
    response = client_a.post(reverse("inventory:countprogram_create"), data={
        "name": "HTTP weekly walk", "location": stocktake_zone_a.pk,
        "abc_class": "", "frequency": "weekly", "weekday": "0",
        "day_of_month": "", "count_method": "zone", "is_active": "on",
        "notes": "created by the view test",
    })
    assert response.status_code == 302
    assert response.url == reverse("inventory:countprogram_list")

    created = CountProgram.objects.get(tenant=tenant_a, name="HTTP weekly walk")
    assert created.number.startswith("CTP-")
    assert created.location_id == stocktake_zone_a.pk


def test_stocktake_program_edit_prefills_instance_then_saves(
        client_a, tenant_a, stocktake_program_a, stocktake_zone_a):
    url = reverse("inventory:countprogram_edit", args=[stocktake_program_a.pk])
    rendered = client_a.get(url)
    assert rendered.status_code == 200
    assert rendered.context["form"].instance.pk == stocktake_program_a.pk
    assert rendered.context["is_edit"] is True
    assert stocktake_program_a.name.encode() in rendered.content

    saved = client_a.post(url, data={
        "name": "Renamed cadence", "location": stocktake_zone_a.pk,
        "abc_class": "", "frequency": "weekly", "weekday": "0",
        "day_of_month": "", "count_method": "abc", "is_active": "on",
        "notes": stocktake_program_a.notes,
    })
    assert saved.status_code == 302
    assert saved.url == reverse("inventory:countprogram_list")
    stocktake_program_a.refresh_from_db()
    assert stocktake_program_a.name == "Renamed cadence"
    assert stocktake_program_a.count_method == "abc"


def test_stocktake_program_delete_get_405_post_removes(
        client_a, tenant_a, stocktake_program_a):
    delete_url = reverse("inventory:countprogram_delete",
                         args=[stocktake_program_a.pk])
    assert client_a.get(delete_url).status_code == 405

    deleted = client_a.post(delete_url)
    assert deleted.status_code == 302
    assert deleted.url == reverse("inventory:countprogram_list")
    assert not CountProgram.objects.filter(pk=stocktake_program_a.pk).exists()


def test_stocktake_program_detail_context_and_number_rendered(
        client_a, tenant_a, stocktake_program_a):
    response = client_a.get(reverse("inventory:countprogram_detail",
                                    args=[stocktake_program_a.pk]))
    assert response.status_code == 200
    assert stocktake_program_a.number.encode() in response.content
    assert response.context["obj"].pk == stocktake_program_a.pk
    assert list(response.context["recent_tasks"]) == []
    assert "is_due" in response.context


# ------------------------------------------------------------------ countprogram run verb


def test_stocktake_run_mints_sheet_stamps_last_run_redirects_into_scm(
        client_a, tenant_a, stocktake_program_a):
    response = client_a.post(reverse("inventory:countprogram_run",
                                     args=[stocktake_program_a.pk]))
    assert response.status_code == 302
    assert "/scm/cycle-counts/" in response.url

    task = CycleCountTask.objects.get(
        tenant_id=tenant_a.pk,
        notes__startswith=f"Via count program {stocktake_program_a.number}")
    assert response.url == reverse("scm:cyclecounttask_detail", args=[task.pk])

    stocktake_program_a.refresh_from_db()
    assert stocktake_program_a.last_run_date == timezone.localdate()


def test_stocktake_run_inactive_program_flash_refused_mints_nothing(
        client_a, tenant_a, stocktake_program_a):
    CountProgram.objects.filter(pk=stocktake_program_a.pk).update(is_active=False)
    stocktake_program_a.refresh_from_db()

    response = client_a.post(reverse("inventory:countprogram_run",
                                     args=[stocktake_program_a.pk]), follow=True)
    assert response.status_code == 200
    assert response.redirect_chain[-1][0].endswith(
        reverse("inventory:countprogram_detail", args=[stocktake_program_a.pk]))
    assert any("inactive" in text for text in _stocktake_flashes(response))

    stocktake_program_a.refresh_from_db()
    assert stocktake_program_a.last_run_date is None
    assert not CycleCountTask.objects.filter(
        tenant_id=tenant_a.pk,
        notes__startswith=f"Via count program {stocktake_program_a.number}").exists()


# ------------------------------------------------------------------ physicalinventory CRUD


def test_stocktake_event_list_renders_row_with_status_choices_and_frozen_count(
        client_a, tenant_a, stocktake_event_a):
    response = client_a.get(reverse("inventory:physicalinventory_list"))
    assert response.status_code == 200
    assert stocktake_event_a.number.encode() in response.content
    assert stocktake_event_a in list(response.context["object_list"])
    assert "page_obj" in response.context and "q" in response.context
    assert dict(response.context["status_choices"])["draft"] == "Draft"
    assert response.context["frozen_count"] == 0


def test_stocktake_event_list_search_hit_by_notes_and_miss(
        client_a, stocktake_event_a):
    url = reverse("inventory:physicalinventory_list")
    hit = client_a.get(url + "?q=wall-to-wall")
    assert hit.status_code == 200
    assert [obj.pk for obj in hit.context["object_list"]] == [stocktake_event_a.pk]

    miss = client_a.get(url + "?q=zzz-nothing")
    assert miss.status_code == 200
    assert list(miss.context["object_list"]) == []


def test_stocktake_event_create_get_renders_form_post_valid_creates_draft(
        client_a, tenant_a, admin_user, stocktake_warehouse_a):
    create_url = reverse("inventory:physicalinventory_create")
    rendered = client_a.get(create_url)
    assert rendered.status_code == 200
    assert rendered.context["form"] is not None
    assert rendered.context["is_edit"] is False

    response = client_a.post(create_url,
                             data=_stocktake_event_payload(stocktake_warehouse_a))
    assert response.status_code == 302
    assert response.url == reverse("inventory:physicalinventory_list")

    created = PhysicalInventory.objects.get(
        tenant=tenant_a, warehouse=stocktake_warehouse_a)
    assert created.number.startswith("PHY-")
    assert created.status == "draft"
    assert created.is_frozen is False
    assert created.requested_by == admin_user   # stamped by the view


def test_stocktake_event_edit_prefills_and_saves_while_draft(
        client_a, tenant_a, stocktake_event_a, stocktake_warehouse_a):
    url = reverse("inventory:physicalinventory_edit", args=[stocktake_event_a.pk])
    rendered = client_a.get(url)
    assert rendered.status_code == 200
    assert rendered.context["form"].instance.pk == stocktake_event_a.pk
    assert rendered.context["obj"].pk == stocktake_event_a.pk

    saved = client_a.post(url, data=_stocktake_event_payload(
        stocktake_warehouse_a, notes="Rescheduled wall-to-wall"))
    assert saved.status_code == 302
    assert saved.url == reverse("inventory:physicalinventory_list")
    stocktake_event_a.refresh_from_db()
    assert stocktake_event_a.notes == "Rescheduled wall-to-wall"
    assert stocktake_event_a.status == "draft"


def test_stocktake_event_edit_refused_once_counting(
        client_a, stocktake_event_counting_a, stocktake_warehouse_a):
    response = client_a.post(
        reverse("inventory:physicalinventory_edit",
                args=[stocktake_event_counting_a.pk]),
        data=_stocktake_event_payload(stocktake_warehouse_a, notes="rewrite attempt"),
        follow=True)
    assert response.status_code == 200
    assert response.redirect_chain[-1][0].endswith(
        reverse("inventory:physicalinventory_detail",
                args=[stocktake_event_counting_a.pk]))
    assert any("cannot be edited" in text for text in _stocktake_flashes(response))
    stocktake_event_counting_a.refresh_from_db()
    assert stocktake_event_counting_a.notes == "Mid-year freeze count"


def test_stocktake_event_delete_get_405_post_removes_draft(
        client_a, tenant_a, stocktake_event_a):
    delete_url = reverse("inventory:physicalinventory_delete",
                         args=[stocktake_event_a.pk])
    assert client_a.get(delete_url).status_code == 405

    deleted = client_a.post(delete_url)
    assert deleted.status_code == 302
    assert deleted.url == reverse("inventory:physicalinventory_list")
    assert not PhysicalInventory.objects.filter(pk=stocktake_event_a.pk).exists()


def test_stocktake_event_delete_of_counting_event_refused_row_survives(
        client_a, stocktake_event_counting_a):
    response = client_a.post(
        reverse("inventory:physicalinventory_delete",
                args=[stocktake_event_counting_a.pk]), follow=True)
    assert response.status_code == 200
    assert response.redirect_chain[-1][0].endswith(
        reverse("inventory:physicalinventory_detail",
                args=[stocktake_event_counting_a.pk]))
    assert any("only a draft event can be deleted" in text
               for text in _stocktake_flashes(response))
    assert PhysicalInventory.objects.filter(pk=stocktake_event_counting_a.pk).exists()


# ------------------------------------------------------------------ physicalinventory detail


def test_stocktake_event_detail_renders_number_and_sheet_coverage(
        client_a, stocktake_zone_a, stocktake_bin_a, stocktake_event_counting_a):
    response = client_a.get(reverse("inventory:physicalinventory_detail",
                                    args=[stocktake_event_counting_a.pk]))
    assert response.status_code == 200
    body = response.content.decode()
    assert stocktake_event_counting_a.number in body
    assert "Frozen" in body
    assert "0/2 reconciled" in body          # zone + bin spawned at start()

    assert response.context["sheet_total"] == 2
    assert response.context["sheet_reconciled"] == 0
    assert response.context["obj"].pk == stocktake_event_counting_a.pk
    assert len(list(response.context["sheets"])) == 2


# ------------------------------------------------------------------ lifecycle verbs


def test_stocktake_start_on_draft_freezes_spawns_two_and_second_start_refused(
        client_a, tenant_a, stocktake_event_a, stocktake_zone_a, stocktake_bin_a):
    start_url = reverse("inventory:physicalinventory_start", args=[stocktake_event_a.pk])

    started = client_a.post(start_url, follow=True)
    assert started.status_code == 200
    assert started.redirect_chain[-1][0].endswith(
        reverse("inventory:physicalinventory_detail", args=[stocktake_event_a.pk]))
    assert any("started" in text and "frozen" in text
               for text in _stocktake_flashes(started))

    stocktake_event_a.refresh_from_db()
    assert stocktake_event_a.status == "counting"
    assert stocktake_event_a.is_frozen is True
    assert stocktake_event_a.started_at is not None
    sheets = list(stocktake_event_a.spawned_tasks())
    assert len(sheets) == 2
    assert all(sheet.number.startswith("CC-") for sheet in sheets)
    assert all(sheet.count_method == "full" for sheet in sheets)

    again = client_a.post(start_url, follow=True)
    assert any("cannot be started" in text for text in _stocktake_flashes(again))
    stocktake_event_a.refresh_from_db()
    assert stocktake_event_a.status == "counting"
    assert stocktake_event_a.spawned_tasks().count() == 2   # no duplicate spawn


def test_stocktake_reconcile_refused_while_sheet_counted_names_it(
        client_a, stocktake_zone_a, stocktake_bin_a, stocktake_event_counting_a):
    stocktake_event_counting_a.spawned_tasks().filter(
        location=stocktake_zone_a).update(status="counted")

    response = client_a.post(
        reverse("inventory:physicalinventory_reconcile",
                args=[stocktake_event_counting_a.pk]), follow=True)
    assert response.status_code == 200
    flash = "; ".join(_stocktake_flashes(response))
    assert "still open" in flash and "CC-" in flash

    stocktake_event_counting_a.refresh_from_db()
    assert stocktake_event_counting_a.status == "counting"
    assert stocktake_event_counting_a.is_frozen is True


def test_stocktake_reconcile_succeeds_once_every_sheet_reconciled_or_cancelled(
        client_a, stocktake_zone_a, stocktake_bin_a, stocktake_event_counting_a):
    sheets = list(stocktake_event_counting_a.spawned_tasks())
    CycleCountTask.objects.filter(pk=sheets[0].pk).update(status="cancelled")
    CycleCountTask.objects.exclude(pk=sheets[0].pk).filter(
        pk__in=[sheet.pk for sheet in sheets[1:]]).update(status="reconciled")

    response = client_a.post(
        reverse("inventory:physicalinventory_reconcile",
                args=[stocktake_event_counting_a.pk]), follow=True)
    assert response.status_code == 200
    assert any("reconciled" in text and "freeze lifted" in text
               for text in _stocktake_flashes(response))

    stocktake_event_counting_a.refresh_from_db()
    assert stocktake_event_counting_a.status == "reconciled"
    assert stocktake_event_counting_a.is_frozen is False
    assert stocktake_event_counting_a.closed_at is not None


def test_stocktake_cancel_from_draft_cancels_and_stays_unfrozen(
        client_a, tenant_a, stocktake_event_a):
    response = client_a.post(
        reverse("inventory:physicalinventory_cancel", args=[stocktake_event_a.pk]),
        follow=True)
    assert response.status_code == 200
    assert any("cancelled" in text for text in _stocktake_flashes(response))

    stocktake_event_a.refresh_from_db()
    assert stocktake_event_a.status == "cancelled"
    assert stocktake_event_a.is_frozen is False
    assert stocktake_event_a.closed_at is not None
    assert stocktake_event_a.spawned_tasks().count() == 0   # cancelled before start


def test_stocktake_all_verbs_are_post_only(client_a, stocktake_program_a,
                                          stocktake_event_a):
    post_only = [
        ("countprogram_delete", stocktake_program_a.pk),
        ("countprogram_run", stocktake_program_a.pk),
        ("physicalinventory_delete", stocktake_event_a.pk),
        ("physicalinventory_start", stocktake_event_a.pk),
        ("physicalinventory_reconcile", stocktake_event_a.pk),
        ("physicalinventory_cancel", stocktake_event_a.pk),
    ]
    for name, pk in post_only:
        response = client_a.get(reverse(f"inventory:{name}", args=[pk]))
        assert response.status_code == 405, name
    # Nothing mutated along the way.
    stocktake_event_a.refresh_from_db()
    assert stocktake_event_a.status == "draft"


# ------------------------------------------------------------------ variance report


def test_stocktake_variance_report_row_dicts_carry_the_full_key_set(
        client_a, tenant_a, stocktake_zone_a, item_a):
    from apps.scm.models import Item

    task = _stocktake_sheet(tenant_a, stocktake_zone_a, status="counted")
    _stocktake_line(task, item_a, expected="10", counted="8")     # short 2
    other = Item.objects.create(tenant=tenant_a, sku="STK-VAR",
                                name="Uncounted thing", standard_cost=Decimal("3.00"))
    _stocktake_line(task, other, expected="5")                    # blind, not yet counted

    response = client_a.get(reverse("inventory:variance_report"))
    assert response.status_code == 200
    rows = [row for row in response.context["object_list"]
            if row["task"].pk == task.pk]
    assert len(rows) == 1
    row = rows[0]
    assert set(row) == {"task", "line_count", "counted_lines", "variance_lines",
                        "net_variance", "abs_variance"}
    assert row["line_count"] == 2
    assert row["counted_lines"] == 1
    assert row["variance_lines"] == 1
    assert row["net_variance"] == Decimal("-2")
    assert row["abs_variance"] == Decimal("2")

    assert "page_obj" in response.context and "q" in response.context
    assert response.context["status"] == ""
    assert ("counted", "Counted (unreconciled)") in response.context["status_choices"]
    assert task.number.encode() in response.content


def test_stocktake_variance_report_q_search_hit_and_miss(
        client_a, tenant_a, stocktake_zone_a, item_a):
    task = _stocktake_sheet(tenant_a, stocktake_zone_a, status="counted")
    _stocktake_line(task, item_a, expected="4", counted="7")

    hit = client_a.get(reverse("inventory:variance_report")
                       + f"?q={stocktake_zone_a.code}")
    assert hit.status_code == 200
    assert any(row["task"].pk == task.pk
               for row in hit.context["object_list"])

    miss = client_a.get(reverse("inventory:variance_report") + "?q=zzz-nothing")
    assert miss.status_code == 200
    assert list(miss.context["object_list"]) == []


# ------------------------------------------------------------------ tenant scoping


def test_stocktake_foreign_workspace_routes_404(
        client_a, stocktake_program_b, stocktake_event_b):
    prog_url = reverse("inventory:countprogram_detail", args=[stocktake_program_b.pk])
    assert client_a.get(prog_url).status_code == 404
    assert client_a.get(reverse("inventory:countprogram_edit",
                                args=[stocktake_program_b.pk])).status_code == 404
    assert client_a.post(reverse("inventory:countprogram_run",
                                 args=[stocktake_program_b.pk])).status_code == 404
    assert client_a.post(reverse("inventory:countprogram_delete",
                                 args=[stocktake_program_b.pk])).status_code == 404

    ev_url = reverse("inventory:physicalinventory_detail", args=[stocktake_event_b.pk])
    assert client_a.get(ev_url).status_code == 404
    assert client_a.get(reverse("inventory:physicalinventory_edit",
                                args=[stocktake_event_b.pk])).status_code == 404
    for verb in ("start", "reconcile", "cancel", "delete"):
        assert client_a.post(
            reverse(f"inventory:physicalinventory_{verb}",
                    args=[stocktake_event_b.pk])).status_code == 404, verb


def test_stocktake_foreign_rows_never_leak_into_tenant_a_lists(
        client_a, stocktake_program_b, stocktake_event_b):
    programs = client_a.get(reverse("inventory:countprogram_list"))
    assert stocktake_program_b.pk not in [
        obj.pk for obj in programs.context["object_list"]]
    events = client_a.get(reverse("inventory:physicalinventory_list"))
    assert stocktake_event_b.pk not in [
        obj.pk for obj in events.context["object_list"]]


# ------------------------------------------------------------------ auth gate


def test_stocktake_anonymous_is_redirected_to_login(client):
    response = client.get(reverse("inventory:countprogram_list"))
    assert response.status_code == 302
