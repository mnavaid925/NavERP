"""Inventory 5.4 — views.

The putaway-rule CRUD renders through the shared crud helpers (tenant-scoped list with
search/status-filter/pagination, detail carrying ``obj`` + ``is_admin``, admin-gated
writes), and the computed suggestions queue resolves SCM 4.4's open tasks into an
explainable best-bin answer whose stats describe the whole queue, never just the page.
"""
from decimal import Decimal

import pytest
from django.urls import reverse

from apps.inventory.models import PutawayRule, resolve_putaway_suggestion
from apps.scm.models import PutawayTask

pytestmark = pytest.mark.django_db


# ---- helpers -------------------------------------------------------------------------------------


def _receiving_rule_payload(**overrides):
    """A valid rule POST body — destination + priority are the only required fields."""
    data = {"item": "", "category": "", "source_location": "", "destination": "",
            "priority": "50", "is_active": "on", "notes": ""}
    data.update(overrides)
    return data


def _receiving_no_template_leak(response):
    """No raw Django comment marker may ever reach rendered output."""
    assert b"{#" not in response.content


def _receiving_seed_extra_rules(tenant, destination, count):
    for i in range(count):
        PutawayRule.objects.create(
            tenant=tenant, destination=destination, priority=1000 + i,
            notes=f"Bulk routing rule {i}")


def _receiving_expected_stats(tenant):
    """What the stats strip SHOULD say, recomputed here through the same resolver the
    view uses — so a view-side shortcut (e.g. counting only the visible page) fails."""
    tasks = PutawayTask.objects.filter(tenant=tenant, status__in=PutawayTask.OPEN_STATUSES)
    open_tasks = tasks.count()
    covered = sum(1 for task in tasks if resolve_putaway_suggestion(task)[1].startswith("Rule:"))
    return {"open_tasks": open_tasks, "covered_by_rule": covered,
            "uncovered": open_tasks - covered}


# ---- routes ----------------------------------------------------------------------------------------


def test_receiving_six_routes_render_200_including_second_page(
        client_a, tenant_a, receiving_rule_a, receiving_loc_bin_a):
    assert client_a.get(reverse("inventory:putawayrule_list")).status_code == 200
    assert client_a.get(reverse("inventory:putawayrule_create")).status_code == 200
    detail = client_a.get(reverse("inventory:putawayrule_detail", args=[receiving_rule_a.pk]))
    assert detail.status_code == 200
    edit = client_a.get(reverse("inventory:putawayrule_edit", args=[receiving_rule_a.pk]))
    assert edit.status_code == 200
    queue = client_a.get(reverse("inventory:putaway_suggestions"))
    assert queue.status_code == 200
    _receiving_seed_extra_rules(tenant_a, receiving_loc_bin_a, 16)  # 18 rows -> a real page 2
    second_page = client_a.get(reverse("inventory:putawayrule_list") + "?page=2")
    assert second_page.status_code == 200
    for response in (detail, edit, queue, second_page):
        _receiving_no_template_leak(response)


# ---- rule list --------------------------------------------------------------------------------------


def test_receiving_list_shows_seeded_rule_scope_text(client_a, receiving_rule_a,
                                                     receiving_rule_catchall_a):
    response = client_a.get(reverse("inventory:putawayrule_list"))
    html = response.content.decode()
    assert "CAT-1" in html      # item-scoped tier renders its SKU
    assert "Any item" in html   # catch-all tier's scope label
    assert "RDOCK-A" in html    # source dock code column
    assert "RA-01" in html      # destination bin code column
    _receiving_no_template_leak(response)


def test_receiving_list_active_inactive_filter_splits_rows(
        client_a, tenant_a, receiving_rule_a, receiving_rule_catchall_a, receiving_loc_bin_a):
    dead = PutawayRule.objects.create(tenant=tenant_a, destination=receiving_loc_bin_a,
                                      priority=500, is_active=False)
    base = reverse("inventory:putawayrule_list")
    total = PutawayRule.objects.filter(tenant=tenant_a).count()

    active = client_a.get(base + "?is_active=active")
    inactive = client_a.get(base + "?is_active=inactive")
    unfiltered = client_a.get(base)
    assert active.status_code == inactive.status_code == unfiltered.status_code == 200

    n_active = len(active.context["object_list"])
    n_inactive = len(inactive.context["object_list"])
    assert n_active == 2 and n_inactive == 1
    assert receiving_rule_a in active.context["object_list"]
    assert dead in inactive.context["object_list"]
    # The split must be exhaustive: active + inactive sums to the tenant's whole table.
    assert n_active + n_inactive == total == len(unfiltered.context["object_list"])


def test_receiving_list_q_matches_item_sku_substring(client_a, receiving_rule_a,
                                                     receiving_rule_catchall_a):
    base = reverse("inventory:putawayrule_list")
    hit = client_a.get(base + "?q=CAT")  # substring of CAT-1, not a full-code match
    assert hit.status_code == 200
    assert list(hit.context["object_list"]) == [receiving_rule_a]
    lowercased = client_a.get(base + "?q=cat")
    assert lowercased.context["object_list"].count() == 1


def test_receiving_list_junk_q_empty_state_renders(client_a, receiving_rule_a):
    response = client_a.get(reverse("inventory:putawayrule_list") + "?q=zzznope")
    assert response.status_code == 200
    assert len(response.context["object_list"]) == 0
    assert b"No putaway rules yet" in response.content
    _receiving_no_template_leak(response)


def test_receiving_list_page_999_clamps_to_last_page(
        client_a, tenant_a, receiving_rule_a, receiving_rule_catchall_a, receiving_loc_bin_a):
    _receiving_seed_extra_rules(tenant_a, receiving_loc_bin_a, 16)  # total 18 -> two pages
    response = client_a.get(reverse("inventory:putawayrule_list") + "?page=999")
    assert response.status_code == 200
    page_obj = response.context["page_obj"]
    assert page_obj.paginator.num_pages == 2
    assert page_obj.number == 2
    assert len(response.context["object_list"]) == 3
    _receiving_no_template_leak(response)


# ---- rule detail -------------------------------------------------------------------------------------


def test_receiving_detail_context_obj_pk_and_is_admin_true(client_a, receiving_rule_a):
    response = client_a.get(reverse("inventory:putawayrule_detail",
                                    args=[receiving_rule_a.pk]))
    assert response.status_code == 200
    assert response.context["obj"].pk == receiving_rule_a.pk
    assert response.context["is_admin"] is True
    _receiving_no_template_leak(response)


# ---- create flow --------------------------------------------------------------------------------------


def test_receiving_create_get_renders_blank_form(client_a):
    response = client_a.get(reverse("inventory:putawayrule_create"))
    assert response.status_code == 200
    assert response.context["is_edit"] is False
    assert not response.context["form"].is_bound
    _receiving_no_template_leak(response)


def test_receiving_create_valid_post_redirects_and_persists_priority_55(
        client_a, tenant_a, item_a, receiving_loc_dock_a, receiving_loc_bin_a):
    response = client_a.post(
        reverse("inventory:putawayrule_create"),
        data=_receiving_rule_payload(item=item_a.pk,
                                     source_location=receiving_loc_dock_a.pk,
                                     destination=receiving_loc_bin_a.pk,
                                     priority="55", notes="Lane probe rule"))
    assert response.status_code == 302
    assert response.url == reverse("inventory:putawayrule_list")
    created = PutawayRule.objects.get(tenant=tenant_a, item=item_a, priority=55)
    assert created.source_location_id == receiving_loc_dock_a.pk
    assert created.destination_id == receiving_loc_bin_a.pk
    assert created.notes == "Lane probe rule"
    assert created.is_active is True


def test_receiving_create_missing_destination_rerenders_with_error(client_a, tenant_a):
    """[C1 view-level] Dropping the required field re-renders the form with its error."""
    total_before = PutawayRule.objects.filter(tenant=tenant_a).count()
    response = client_a.post(reverse("inventory:putawayrule_create"),
                             data=_receiving_rule_payload(priority="55"))
    assert response.status_code == 200
    assert b"This field is required" in response.content
    assert response.context["form"].errors["destination"]
    assert PutawayRule.objects.filter(tenant=tenant_a).count() == total_before


# ---- edit flow -----------------------------------------------------------------------------------------


def test_receiving_edit_get_prefills_instance_values(client_a, receiving_rule_a,
                                                     receiving_loc_dock_a,
                                                     receiving_loc_bin_a):
    response = client_a.get(reverse("inventory:putawayrule_edit", args=[receiving_rule_a.pk]))
    assert response.status_code == 200
    assert response.context["is_edit"] is True
    assert response.context["obj"].pk == receiving_rule_a.pk
    form = response.context["form"]
    assert not form.is_bound
    assert form["item"].value() == receiving_rule_a.item_id
    assert form["source_location"].value() == receiving_loc_dock_a.pk
    assert form["destination"].value() == receiving_loc_bin_a.pk
    assert form["priority"].value() == receiving_rule_a.priority
    assert form["notes"].value() == receiving_rule_a.notes


def test_receiving_edit_post_updates_priority_and_notes(client_a, receiving_rule_a,
                                                        receiving_loc_dock_a,
                                                        receiving_loc_bin_a):
    response = client_a.post(
        reverse("inventory:putawayrule_edit", args=[receiving_rule_a.pk]),
        data=_receiving_rule_payload(item=receiving_rule_a.item_id,
                                     source_location=receiving_loc_dock_a.pk,
                                     destination=receiving_loc_bin_a.pk,
                                     priority="66", notes="Rewritten routing note"))
    assert response.status_code == 302
    assert response.url == reverse("inventory:putawayrule_list")
    receiving_rule_a.refresh_from_db()
    assert receiving_rule_a.priority == 66
    assert receiving_rule_a.notes == "Rewritten routing note"
    detail = client_a.get(reverse("inventory:putawayrule_detail",
                                  args=[receiving_rule_a.pk]))
    html = detail.content.decode()
    assert "Rewritten routing note" in html
    priority_line = next(line for line in html.splitlines() if "lower runs first" in line)
    assert ">66 " in priority_line


# ---- delete --------------------------------------------------------------------------------------------


def test_receiving_delete_post_removes_row_and_redirects(client_a, tenant_a,
                                                         receiving_rule_catchall_a):
    response = client_a.post(reverse("inventory:putawayrule_delete",
                                     args=[receiving_rule_catchall_a.pk]))
    assert response.status_code == 302
    assert response.url == reverse("inventory:putawayrule_list")
    assert not PutawayRule.objects.filter(tenant=tenant_a,
                                          pk=receiving_rule_catchall_a.pk).exists()


def test_receiving_delete_get_is_post_only_405(client_a, receiving_rule_a):
    assert client_a.get(reverse("inventory:putawayrule_delete",
                                args=[receiving_rule_a.pk])).status_code == 405
    assert PutawayRule.objects.filter(pk=receiving_rule_a.pk).exists()


# ---- suggestions queue ----------------------------------------------------------------------------------


def test_receiving_suggestions_lists_task_number_and_grn_em_dash(client_a, receiving_task_a):
    response = client_a.get(reverse("inventory:putaway_suggestions"))
    assert response.status_code == 200
    assert receiving_task_a.number.startswith("PUT-")
    assert receiving_task_a.number.encode() in response.content
    row = response.context["rows"][0]
    assert row["task"].pk == receiving_task_a.pk
    assert row["receipt"] is None  # fixture carries no goods receipt…
    assert "\u2014" in response.content.decode()  # …so the GRN cell renders its em-dash safely
    _receiving_no_template_leak(response)


def test_receiving_suggestions_stats_trio_match_resolver_expectations(
        client_a, tenant_a, receiving_task_a, receiving_rule_a, receiving_rule_catchall_a):
    expected = _receiving_expected_stats(tenant_a)
    assert expected["open_tasks"] >= 1
    response = client_a.get(reverse("inventory:putaway_suggestions"))
    assert response.status_code == 200
    assert response.context["stats"] == expected
    html = response.content.decode()
    for label in ("Open tasks", "Covered by rule", "Uncovered"):
        assert label in html
    _receiving_no_template_leak(response)


def test_receiving_suggestions_row_carries_rule_hit_reason_string(
        client_a, receiving_task_a, receiving_rule_a):
    response = client_a.get(reverse("inventory:putaway_suggestions"))
    assert response.status_code == 200
    reasons = [row["suggestion_reason"] for row in response.context["rows"]]
    assert any(reason.startswith("Rule:") for reason in reasons)
    hit = next(row for row in response.context["rows"]
               if row["suggestion_reason"].startswith("Rule:"))
    assert hit["suggestion"] is not None
    assert "Rule: CAT-1 arriving RDOCK-A \u2192 RA-01" in response.content.decode()


def test_receiving_suggestions_warehouse_filter_keeps_dock_staged_task(
        client_a, receiving_task_a, receiving_loc_warehouse_a):
    response = client_a.get(reverse("inventory:putaway_suggestions")
                            + f"?warehouse={receiving_loc_warehouse_a.pk}")
    assert response.status_code == 200
    assert [row["task"].pk for row in response.context["rows"]] == [receiving_task_a.pk]
    _receiving_no_template_leak(response)


def test_receiving_suggestions_warehouse_filter_keeps_task_staged_at_warehouse_root(
        client_a, tenant_a, item_a, receiving_task_a, receiving_loc_warehouse_a,
        receiving_loc_bin_a):
    """M2 regression: ancestry-contains means a task staged AT the warehouse row itself
    belongs to that warehouse's filter too, not only dock-level descendants."""
    root_task = PutawayTask.objects.create(
        tenant=tenant_a, item=item_a, from_location=receiving_loc_warehouse_a,
        to_location=receiving_loc_bin_a, quantity=Decimal("4"), status="pending")
    expected_pks = {receiving_task_a.pk, root_task.pk}
    unfiltered = client_a.get(reverse("inventory:putaway_suggestions"))
    filtered = client_a.get(reverse("inventory:putaway_suggestions")
                            + f"?warehouse={receiving_loc_warehouse_a.pk}")
    assert {row["task"].pk for row in unfiltered.context["rows"]} == expected_pks
    assert {row["task"].pk for row in filtered.context["rows"]} == expected_pks


def test_receiving_suggestions_junk_warehouse_param_is_harmless(client_a, receiving_task_a):
    for junk in ("999", "abc"):
        response = client_a.get(reverse("inventory:putaway_suggestions")
                                + f"?warehouse={junk}")
        assert response.status_code == 200
        assert response.context["stats"]["open_tasks"] == 1
        assert [row["task"].pk for row in response.context["rows"]] == [receiving_task_a.pk]


# ---- gating -----------------------------------------------------------------------------------------------


def test_receiving_member_writes_blocked_reads_open_and_list_context_is_admin_false(
        member_client, receiving_rule_a):
    """tenant_admin_required raises PermissionDenied BEFORE require_POST, so every write
    verb reads as 403 to a member while list/detail stay open at 200 with is_admin False."""
    listing = member_client.get(reverse("inventory:putawayrule_list"))
    assert listing.status_code == 200
    assert listing.context["is_admin"] is False
    assert member_client.get(reverse("inventory:putawayrule_detail",
                                     args=[receiving_rule_a.pk])).status_code == 200

    gated_urls = [
        reverse("inventory:putawayrule_create"),
        reverse("inventory:putawayrule_edit", args=[receiving_rule_a.pk]),
        reverse("inventory:putawayrule_delete", args=[receiving_rule_a.pk]),
    ]
    for url in gated_urls:
        assert member_client.get(url).status_code == 403, url
        assert member_client.post(url).status_code == 403, url
    assert PutawayRule.objects.filter(pk=receiving_rule_a.pk).exists()
