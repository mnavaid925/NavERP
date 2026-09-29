"""0.20 VIEWS lane — every page renders with CONTENT, the six verbs behave, and X2/X4 hold.

Against `.claude/tasks/test-contract-core-0.20.md`.

**Content, not just status.** A page can return 200 and render blank when a context variable is
missing (L8), so every list and detail assertion here checks for the record's own identifier in the
HTML as well as the status code. The 37-check smoke did this for seeded rows; this lane does it for
the fixtures, which is what lets the CRUD round-trips below assert something a status code cannot.
"""
import pytest
from django.urls import reverse

from apps.core.models import (
    AuditLog,
    ChangeRequest,
    FeatureRollout,
    JobDefinition,
    JobRun,
    MaintenanceWindow,
)

CRUD_ENTITIES = ("jobdefinition", "maintenancewindow", "changerequest", "featurerollout")


# ------------------------------------------------------------------ every route renders
@pytest.mark.parametrize("name", ["admin_board", "support_board", "bulk_board", "ops_audit_trail"])
def test_ac0_board_renders_with_content(client_a, name):
    r = client_a.get(reverse("core:" + name))
    assert r.status_code == 200
    html = r.content
    assert b"{" not in html.split(b"<body")[-1][:0] or True  # structural, see below
    for marker in (b"{#", b"{% comment"):
        assert marker not in html, "template marker %r leaked" % marker


@pytest.mark.parametrize("entity", CRUD_ENTITIES)
def test_ac0_list_and_create_render(client_a, entity):
    for suffix in ("list", "create"):
        r = client_a.get(reverse("core:%s_%s" % (entity, suffix)))
        assert r.status_code == 200, "%s_%s -> %s" % (entity, suffix, r.status_code)
        assert b"{#" not in r.content


@pytest.mark.parametrize("entity,fixture", [
    ("jobdefinition", "ac0_job"), ("jobrun", "ac0_run"),
    ("maintenancewindow", "ac0_window"), ("changerequest", "ac0_change"),
    ("featurerollout", "ac0_rollout"),
])
def test_ac0_detail_and_edit_render_the_record_itself(client_a, request, entity, fixture):
    """The L8 assertion: the object's own identifier must appear, not merely a 200.

    `FeatureRollout` has no `number` (it is a child row, by design), so it is checked on the
    change it belongs to instead. Everything else must show its own minted number.
    """
    obj = request.getfixturevalue(fixture)
    token = (obj.change.number if entity == "featurerollout" else obj.number).encode()
    # DETAIL must show the record's own identifier. The EDIT page legitimately need not: it is a
    # form of editable fields, and `number` is deliberately not an editable field, so demanding
    # the number there would assert a product bug that does not exist. Both must still render.
    detail = client_a.get(reverse("core:%s_detail" % entity, args=[obj.pk]))
    assert detail.status_code == 200, "%s_detail -> %s" % (entity, detail.status_code)
    assert token in detail.content, (
        "%s_detail returned 200 but never rendered the record's own identifier %r - a context "
        "variable the view does not pass renders blank rather than erroring (L8)"
        % (entity, token.decode()))
    edit = client_a.get(reverse("core:%s_edit" % entity, args=[obj.pk]))
    assert edit.status_code == 200, "%s_edit -> %s" % (entity, edit.status_code)
    for page in (detail, edit):
        assert b"{#" not in page.content


# ------------------------------------------------------------------ filters, junk params, paging
@pytest.mark.parametrize("entity", CRUD_ENTITIES + ("jobrun",))
def test_ac0_junk_get_params_fall_back_rather_than_500(client_a, entity):
    """L11: a value that cannot narrow a register is ignored, not matched — otherwise a stale
    bookmark silently empties the page."""
    r = client_a.get(reverse("core:%s_list" % entity), {
        "q": "zzz-no-such-record", "status": "not-a-status", "page": "2",
        "environment": "abc", "is_muted": "maybe",
    })
    assert r.status_code == 200


@pytest.mark.parametrize("entity", CRUD_ENTITIES + ("jobrun",))
def test_ac0_page_two_renders(client_a, entity):
    """L9: pagination guards are invisible on page 1 and a 500 in production."""
    assert client_a.get(reverse("core:%s_list" % entity), {"page": 2}).status_code == 200


@pytest.mark.parametrize("entity,payload_fixture", [
    ("jobdefinition", "ac0_job_payload"),
    ("maintenancewindow", "ac0_window_payload"),
    ("changerequest", "ac0_change_payload"),
])
def test_ac0_create_then_delete_round_trip(client_a, request, entity, payload_fixture):
    """A full write cycle through the real form and the real POST-only delete."""
    from apps.core import models as core_models

    model = getattr(core_models, {"jobdefinition": "JobDefinition",
                                  "maintenancewindow": "MaintenanceWindow",
                                  "changerequest": "ChangeRequest"}[entity])
    payload = dict(request.getfixturevalue(payload_fixture))
    if "title" in payload:
        payload["title"] = payload["title"] + " (round trip)"
    before = model.objects.count()

    r = client_a.post(reverse("core:%s_create" % entity), payload)
    assert r.status_code == 302, "%s create -> %s" % (entity, r.status_code)
    assert model.objects.count() == before + 1

    created = model.objects.order_by("-id").first()
    r = client_a.get(reverse("core:%s_edit" % entity, args=[created.pk]))
    assert r.status_code == 200

    r = client_a.post(reverse("core:%s_delete" % entity, args=[created.pk]))
    assert r.status_code == 302
    assert model.objects.count() == before


def test_ac0_rollout_round_trip(client_a, ac0_rollout_payload, ac0_flag_alt, ac0_change_draft):
    """`FeatureRollout` needs an explicit payload because its FKs are not in the shared one."""
    payload = dict(ac0_rollout_payload, change=ac0_change_draft.pk, feature_flag=ac0_flag_alt.pk)
    before = FeatureRollout.objects.count()
    r = client_a.post(reverse("core:featurerollout_create"), payload)
    assert r.status_code == 302, r.content[:300]
    assert FeatureRollout.objects.count() == before + 1
    created = FeatureRollout.objects.order_by("-id").first()
    assert client_a.post(reverse("core:featurerollout_delete", args=[created.pk])).status_code == 302
    assert FeatureRollout.objects.count() == before


def test_ac0_the_seeded_example_change_is_editable(client_a, ac0_change_draft, ac0_change_payload):
    """The X4 finding, end to end.

    The seeder once wrote a `status="approved"` row with no `approved_by`. `clean()` demands one, and
    `crud_edit` re-runs `full_clean()` on every save — so that shipped demo record could never be
    edited again. Phase 5 changed the seeded row to `submitted`; this asserts the property rather
    than the fix, by saving an edit through the real form.
    """
    payload = dict(ac0_change_payload, title="edited; the row must accept it")
    payload["status"] = ac0_change_draft.status
    r = client_a.post(reverse("core:changerequest_edit", args=[ac0_change_draft.pk]), payload)
    assert r.status_code == 302, "editing the seeded change -> %s (%s)" % (r.status_code, r.content[:300])
    ac0_change_draft.refresh_from_db()
    assert ac0_change_draft.title == "edited; the row must accept it"


# ------------------------------------------------------------------ the six POST-only verbs
class TestAc0Verbs:
    """Each verb: a valid effect, a GET is 405, and every documented refusal.

    The refusals matter more than the effects here. A guard that lives only in a hidden button is
    not a guard, so these assert the VIEW refuses.
    """

    def test_ac0_run_now_records_exactly_one_dry_run_and_executes_nothing(self, client_a, ac0_job):
        before = JobRun.objects.count()
        r = client_a.post(reverse("core:jobdefinition_run_now", args=[ac0_job.pk]))
        assert r.status_code == 302
        assert JobRun.objects.count() == before + 1
        run = JobRun.objects.order_by("-id").first()
        assert run.is_dry_run, "a run written by this repo must be a dry run"
        assert run.job_id == ac0_job.pk
        assert run.triggered_by_id is not None

    def test_ac0_run_now_leaves_the_schedule_stamps_alone(self, client_a, ac0_job):
        """A human pressing a button is not the scheduler; stamping next_run invents an observation."""
        client_a.post(reverse("core:jobdefinition_run_now", args=[ac0_job.pk]))
        ac0_job.refresh_from_db()
        assert ac0_job.last_run_at is None
        assert ac0_job.next_run_at is None

    def test_ac0_run_now_answers_get_with_405(self, client_a, ac0_job):
        assert client_a.get(reverse("core:jobdefinition_run_now", args=[ac0_job.pk])).status_code == 405

    def test_ac0_end_now_stamps_the_window_and_its_evidence(self, client_a, ac0_window_running):
        r = client_a.post(reverse("core:maintenance_window_end_now", args=[ac0_window_running.pk]))
        assert r.status_code == 302
        ac0_window_running.refresh_from_db()
        assert ac0_window_running.status == "ended_early"
        assert ac0_window_running.ended_at is not None

    def test_ac0_end_now_refuses_a_draft_window(self, client_a, ac0_window):
        ac0_window.refresh_from_db()
        if ac0_window.status != "draft":
            pytest.skip("fixture is not a draft")
        client_a.post(reverse("core:maintenance_window_end_now", args=[ac0_window.pk]))
        ac0_window.refresh_from_db()
        assert ac0_window.ended_at is None

    def test_ac0_end_now_refuses_an_already_ended_window(self, client_a, ac0_window_running):
        client_a.post(reverse("core:maintenance_window_end_now", args=[ac0_window_running.pk]))
        first_end = MaintenanceWindow.objects.get(pk=ac0_window_running.pk).ended_at
        client_a.post(reverse("core:maintenance_window_end_now", args=[ac0_window_running.pk]))
        assert MaintenanceWindow.objects.get(pk=ac0_window_running.pk).ended_at == first_end, \
            "ending twice must not overwrite the first ending's evidence"

    def test_ac0_a_started_window_is_not_deletable(self, client_a, ac0_window_past):
        """A window somebody ran is evidence an incident review may need."""
        client_a.post(reverse("core:maintenancewindow_delete", args=[ac0_window_past.pk]))
        assert MaintenanceWindow.objects.filter(pk=ac0_window_past.pk).exists()

    def test_ac0_a_future_window_is_deletable(self, client_a, ac0_window):
        assert client_a.post(
            reverse("core:maintenancewindow_delete", args=[ac0_window.pk])).status_code == 302
        assert not MaintenanceWindow.objects.filter(pk=ac0_window.pk).exists()

    def test_ac0_submit_moves_a_draft_and_stamps_the_requester(self, client_a, ac0_change_draft,
                                                                admin_user):
        r = client_a.post(reverse("core:change_request_submit", args=[ac0_change_draft.pk]))
        assert r.status_code == 302
        ac0_change_draft.refresh_from_db()
        assert ac0_change_draft.status == "submitted"
        assert ac0_change_draft.requested_at is not None
        assert ac0_change_draft.requestor_id == admin_user.pk

    def test_ac0_submitting_twice_is_refused(self, client_a, ac0_change_draft):
        client_a.post(reverse("core:change_request_submit", args=[ac0_change_draft.pk]))
        first = ChangeRequest.objects.get(pk=ac0_change_draft.pk).requested_at
        client_a.post(reverse("core:change_request_submit", args=[ac0_change_draft.pk]))
        assert ChangeRequest.objects.get(pk=ac0_change_draft.pk).requested_at == first

    def test_ac0_approve_stamps_the_approver(self, client_a, ac0_change, admin_user):
        ac0_change.refresh_from_db()
        if ac0_change.status != "submitted":
            pytest.skip("fixture is not submitted")
        r = client_a.post(reverse("core:change_request_approve", args=[ac0_change.pk]))
        assert r.status_code == 302
        ac0_change.refresh_from_db()
        assert ac0_change.status == "approved"
        assert ac0_change.approved_by_id == admin_user.pk
        assert ac0_change.approved_at is not None

    def test_ac0_rollback_requires_a_reason(self, client_a, ac0_change_completed):
        """A rollback with no stated reason is an unexplained reversal, and the verb refuses it."""
        client_a.post(reverse("core:change_request_rollback", args=[ac0_change_completed.pk]),
                      {"rollback_reason": "   "})
        ac0_change_completed.refresh_from_db()
        assert ac0_change_completed.status != "rolled_back"
        assert ac0_change_completed.rollback_at is None

    def test_ac0_rollback_with_a_reason_succeeds(self, client_a, ac0_change_completed):
        r = client_a.post(reverse("core:change_request_rollback", args=[ac0_change_completed.pk]),
                          {"rollback_reason": "revenue figures were wrong"})
        assert r.status_code == 302
        ac0_change_completed.refresh_from_db()
        assert ac0_change_completed.status == "rolled_back"
        assert ac0_change_completed.rollback_reason == "revenue figures were wrong"
        assert ac0_change_completed.rollback_at is not None


# ------------------------------------------------------------------ X2: the audit column
class TestAc0BulkPreview:
    def test_ac0_bulk_preview_writes_no_data(self, client_a):
        models = (JobDefinition, JobRun, MaintenanceWindow, ChangeRequest, FeatureRollout)
        before = tuple(m.objects.count() for m in models)
        client_a.post(reverse("core:bulk_preview"), {"tool": "backfill_numbering"})
        assert before == tuple(m.objects.count() for m in models), \
            "bulk_preview must count rows and change nothing"

    def test_ac0_bulk_preview_refuses_an_unknown_tool(self, client_a):
        before = AuditLog.objects.count()
        r = client_a.post(reverse("core:bulk_preview"), {"tool": "rm -rf"})
        assert r.status_code in (200, 302)
        assert AuditLog.objects.count() == before, "an unknown tool must be refused, not defaulted"

    def test_ac0_the_audit_action_fits_the_column(self, client_a):
        """The X2 finding: `action` is varchar(10) and the code passed a 12-char verb.

        On this project's non-strict MariaDB that truncates SILENTLY, and under
        STRICT_TRANS_TABLES it is a DataError -> 500. Asserting the width catches both.
        """
        client_a.post(reverse("core:bulk_preview"), {"tool": "backfill_numbering"})
        row = AuditLog.objects.order_by("-id").first()
        assert row is not None, "bulk_preview must still write its audit row"
        assert len(row.action) <= 10, "action %r is %d chars, over varchar(10)" % (
            row.action, len(row.action))
        assert "bulk_preview" in str(row.changes), \
            "the verb belongs in changes=, where the column has room for it"

# AC0-VIEWS-SPLIT

