"""Procurement 6.18 Inventory & Warehouse Integration — security tests.

This sub-module is unusual: **two of its five models carry no `tenant` column at all.**
`ReplenishmentSuggestion` reaches tenancy only through `run__tenant`, and `MaterialIssueLine` only
through `issue__tenant`. So the IDOR boundary is not "does the queryset filter tenant" — it is
"does every child route resolve through its parent". The sharpest test here smuggles a **real**
line id belonging to tenant B underneath a tenant-A document id: a view that resolved the child by
bare pk would happily mutate another workspace's row while looking correctly scoped.

The other half is the privilege ladder. `release` raises requisitions that commit money and `post`
mints a stock adjustment that changes stock; both are `@tenant_admin_required`. A plain member
must be refused by the *view*, not merely un-offered by the template.
"""
import pytest
from django.urls import reverse

from apps.procurement.models import (
    MaterialIssue,
    MaterialIssueLine,
    ReplenishmentPolicy,
    ReplenishmentRun,
    ReplenishmentSuggestion,
)
from apps.scm.models import StockAdjustment, StockMove

pytestmark = pytest.mark.django_db


def _invwarehouse_url(name, *args):
    return reverse(f"procurement:{name}", args=args)


# --------------------------------------------------------------- cross-tenant reads → 404


@pytest.mark.parametrize("name,fixture", [
    ("replenishmentpolicy_detail", "invwarehouse_policy_b"),
    ("replenishmentrun_detail", "invwarehouse_run_b"),
    ("materialissue_detail", "invwarehouse_issue_b"),
])
def test_invwarehouse_cross_tenant_detail_is_404(client_a, request, name, fixture):
    """404, never 403 — a 403 confirms the row exists, which is itself a disclosure."""
    obj = request.getfixturevalue(fixture)
    assert client_a.get(_invwarehouse_url(name, obj.pk)).status_code == 404


@pytest.mark.parametrize("name,fixture", [
    ("replenishmentpolicy_edit", "invwarehouse_policy_b"),
    ("replenishmentrun_edit", "invwarehouse_run_b"),
    ("materialissue_edit", "invwarehouse_issue_b"),
])
def test_invwarehouse_cross_tenant_edit_is_404(client_a, request, name, fixture):
    obj = request.getfixturevalue(fixture)
    assert client_a.get(_invwarehouse_url(name, obj.pk)).status_code == 404


# --------------------------------------------------------------- cross-tenant writes → 404, no mutation


def test_invwarehouse_cross_tenant_policy_delete_does_not_delete(
        client_a, invwarehouse_policy_b):
    resp = client_a.post(_invwarehouse_url("replenishmentpolicy_delete",
                                           invwarehouse_policy_b.pk))
    assert resp.status_code == 404
    assert ReplenishmentPolicy.objects.filter(pk=invwarehouse_policy_b.pk).exists()


def test_invwarehouse_cross_tenant_run_delete_does_not_delete(client_a, invwarehouse_run_b):
    resp = client_a.post(_invwarehouse_url("replenishmentrun_delete", invwarehouse_run_b.pk))
    assert resp.status_code == 404
    assert ReplenishmentRun.objects.filter(pk=invwarehouse_run_b.pk).exists()


def test_invwarehouse_cross_tenant_issue_delete_does_not_delete(client_a, invwarehouse_issue_b):
    resp = client_a.post(_invwarehouse_url("materialissue_delete", invwarehouse_issue_b.pk))
    assert resp.status_code == 404
    assert MaterialIssue.objects.filter(pk=invwarehouse_issue_b.pk).exists()


@pytest.mark.parametrize("verb", ["replenishmentrun_generate", "replenishmentrun_release",
                                  "replenishmentrun_cancel"])
def test_invwarehouse_cross_tenant_run_verbs_are_refused(client_a, invwarehouse_run_b, verb):
    before = invwarehouse_run_b.status
    resp = client_a.post(_invwarehouse_url(verb, invwarehouse_run_b.pk))
    assert resp.status_code in (403, 404)
    invwarehouse_run_b.refresh_from_db()
    assert invwarehouse_run_b.status == before


@pytest.mark.parametrize("verb", ["materialissue_submit", "materialissue_post",
                                  "materialissue_cancel"])
def test_invwarehouse_cross_tenant_issue_verbs_are_refused(client_a, invwarehouse_issue_b, verb):
    before = invwarehouse_issue_b.status
    moves_before = StockMove.objects.count()
    adj_before = StockAdjustment.objects.count()

    resp = client_a.post(_invwarehouse_url(verb, invwarehouse_issue_b.pk))

    assert resp.status_code in (403, 404)
    invwarehouse_issue_b.refresh_from_db()
    assert invwarehouse_issue_b.status == before
    assert StockMove.objects.count() == moves_before
    assert StockAdjustment.objects.count() == adj_before


# ------------------------------------- THE TENANT-LESS CHILD BOUNDARY (the sharp one)


def test_invwarehouse_foreign_suggestion_smuggled_under_a_local_run_is_404(
        client_a, invwarehouse_run_lines_a, invwarehouse_run_b,
        invwarehouse_item_b, invwarehouse_location_b):
    """A REAL tenant-B line id under a tenant-A run id.

    ReplenishmentSuggestion has no tenant column, so a view that loaded the line by bare pk would
    mutate another workspace's row while looking correctly scoped — the run id in the URL is ours,
    the object is not. The guarantee has to come from resolving the child THROUGH the parent
    (pk=line_id, run__pk=pk, run__tenant=request.tenant), and this is the test that distinguishes
    that from a plain tenant filter.
    """
    # Built here rather than taken from a fixture, and deliberately NOT pytest.skip()ed if
    # absent: this is the sharpest test in the file, and a skip would report as a pass while
    # proving nothing. The line must exist for the assertion to mean anything, so make it exist.
    foreign = ReplenishmentSuggestion.objects.filter(run=invwarehouse_run_b).first()
    if foreign is None:
        b_line = invwarehouse_run_lines_a.lines.first()
        foreign = ReplenishmentSuggestion.objects.create(
            run=invwarehouse_run_b, item=invwarehouse_item_b, location=invwarehouse_location_b,
            on_hand_qty=0, allocated_qty=0, on_order_qty=0, open_requisition_qty=0,
            available_qty=0, reorder_point_snapshot=0, target_level_snapshot=0,
            raw_suggested_qty=b_line.raw_suggested_qty, suggested_qty=b_line.suggested_qty,
            unit_cost=b_line.unit_cost, lead_time_days=0, decision="pending")
    before = foreign.decision

    resp = client_a.post(
        _invwarehouse_url("replenishmentsuggestion_decide", invwarehouse_run_lines_a.pk,
                          foreign.pk),
        {"decision": "accepted", "snooze_until": "", "decision_note": "hijack"})

    assert resp.status_code == 404
    foreign.refresh_from_db()
    assert foreign.decision == before


def test_invwarehouse_foreign_issue_line_smuggled_under_a_local_document_is_404(
        client_a, invwarehouse_issue_draft_a, invwarehouse_issue_b):
    """Same shape for MaterialIssueLine, which also has no tenant column."""
    foreign = MaterialIssueLine.objects.filter(issue=invwarehouse_issue_b).first()
    if foreign is None:
        pytest.skip("tenant B issue has no lines")

    resp = client_a.post(
        _invwarehouse_url("materialissueline_delete", invwarehouse_issue_draft_a.pk, foreign.pk))

    assert resp.status_code == 404
    assert MaterialIssueLine.objects.filter(pk=foreign.pk).exists()


def test_invwarehouse_line_add_cannot_retarget_its_parent(
        client_a, invwarehouse_issue_draft_a, invwarehouse_issue_b, invwarehouse_item_a):
    """`issue` is set from the URL and is absent from the form's Meta.fields.

    So a POST carrying issue=<tenant B's document> cannot move the line — the field is not there
    to bind. This asserts the structural guarantee rather than a filter.
    """
    b_lines_before = MaterialIssueLine.objects.filter(issue=invwarehouse_issue_b).count()

    client_a.post(
        _invwarehouse_url("materialissueline_add", invwarehouse_issue_draft_a.pk),
        {"item": invwarehouse_item_a.pk, "quantity": "1", "notes": "",
         "issue": invwarehouse_issue_b.pk})

    assert MaterialIssueLine.objects.filter(issue=invwarehouse_issue_b).count() == b_lines_before


# --------------------------------------------------------------- the privilege ladder


def test_invwarehouse_member_cannot_release_a_run(
        member_client, invwarehouse_run_proposed_a):
    """Release raises requisitions — the start of spending money.

    The template not offering the button is UX; this asserts the VIEW refuses it, which is what a
    hand-crafted POST meets.
    """
    resp = member_client.post(
        _invwarehouse_url("replenishmentrun_release", invwarehouse_run_proposed_a.pk))
    assert resp.status_code in (403, 302)
    invwarehouse_run_proposed_a.refresh_from_db()
    assert invwarehouse_run_proposed_a.status == "proposed"


def test_invwarehouse_member_cannot_post_an_issue(
        member_client, invwarehouse_issue_submitted_a):
    """Post mints a stock adjustment — it changes stock."""
    moves_before = StockMove.objects.count()
    adj_before = StockAdjustment.objects.count()

    resp = member_client.post(
        _invwarehouse_url("materialissue_post", invwarehouse_issue_submitted_a.pk))

    assert resp.status_code in (403, 302)
    invwarehouse_issue_submitted_a.refresh_from_db()
    assert invwarehouse_issue_submitted_a.status == "submitted"
    assert StockMove.objects.count() == moves_before
    assert StockAdjustment.objects.count() == adj_before


def test_invwarehouse_member_can_still_submit(member_client, invwarehouse_issue_draft_a):
    """Submit is NOT privileged — recording an intent to draw material is ordinary work.

    Gating it would push people to work outside the system, which is worse than the risk.
    """
    member_client.post(
        _invwarehouse_url("materialissue_submit", invwarehouse_issue_draft_a.pk))
    invwarehouse_issue_draft_a.refresh_from_db()
    assert invwarehouse_issue_draft_a.status in ("submitted", "draft")


def test_invwarehouse_member_cannot_write_a_replenishment_policy(
        member_client, invwarehouse_item3_a, invwarehouse_location_a):
    """Regression for finding I4.

    The policy is configuration, but release() stamps it verbatim onto requisitions — vendor, cost
    centre, budget, GL coding and quantity — on a document the admin-gated Release then raises in
    the ADMIN's name. So writing the policy is a privileged act even though it looks like config.
    """
    before = ReplenishmentPolicy.objects.count()
    resp = member_client.post(_invwarehouse_url("replenishmentpolicy_create"), {
        "item": invwarehouse_item3_a.pk, "location": invwarehouse_location_a.pk,
        "source_method": "buy", "trigger_mode": "review", "is_active": "on", "notes": ""})
    assert resp.status_code in (403, 302)
    assert ReplenishmentPolicy.objects.count() == before


# --------------------------------------------------------------- anonymous access


@pytest.mark.parametrize("name", ["replenishmentpolicy_list", "replenishmentrun_list",
                                  "materialissue_list", "stock_position",
                                  "receipt_bin_map", "count_accuracy"])
def test_invwarehouse_anonymous_is_redirected_to_login(client, name):
    resp = client.get(_invwarehouse_url(name))
    assert resp.status_code == 302
    assert "login" in resp["Location"]


def test_invwarehouse_anonymous_cannot_post_a_verb(client, invwarehouse_issue_submitted_a):
    moves_before = StockMove.objects.count()
    resp = client.post(_invwarehouse_url("materialissue_post",
                                         invwarehouse_issue_submitted_a.pk))
    assert resp.status_code == 302
    invwarehouse_issue_submitted_a.refresh_from_db()
    assert invwarehouse_issue_submitted_a.status == "submitted"
    assert StockMove.objects.count() == moves_before


# --------------------------------------------------------------- CSRF


def test_invwarehouse_verb_without_a_csrf_token_is_refused(invwarehouse_issue_submitted_a):
    """CSRF middleware is active on the verb routes.

    The default test client disables CSRF checking, which is why this builds its own with
    ``enforce_csrf_checks=True`` — a suite that only ever used the default client would never
    exercise the middleware at all and would report clean whether or not it was wired up.
    """
    from django.test import Client

    raw = Client(enforce_csrf_checks=True)
    before = invwarehouse_issue_submitted_a.status

    resp = raw.post(_invwarehouse_url("materialissue_post", invwarehouse_issue_submitted_a.pk))

    assert resp.status_code in (302, 403)
    invwarehouse_issue_submitted_a.refresh_from_db()
    assert invwarehouse_issue_submitted_a.status == before
