"""0.16 view-lane tests — Backup, Recovery & Data Lifecycle.

Contract: `.claude/tasks/test-contract-core-0.16.md` §6.

The theme: **every figure on these two boards is a claim, and a claim must be earned.** The sub-module
exists to refuse the reassuring `0` that means "cannot tell", to name the backup nobody checked, and to
show work that is happening right now rather than only work that has finished. So the assertions here are
mostly about what the page must NOT say — and every refusal is paired with a control, because a page that
refused everything would pass a refusal test.
"""
import re

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.urls import NoReverseMatch, reverse
from django.utils import timezone

from apps.core.models import BackupJob, DataArchive, EnvironmentInstance, RecoveryDrill, RestoreRecord
from apps.core.models.LegalHold import LegalHold

#: Every 0.16 route name. 34 of them — the number the contract's M12 pins, against the "29 url names"
#: the frozen draft claimed (some names are reached through the `crud()` factory).
ROUTE_NAMES = [
    "backup_overview", "backup_board",
    "backup_job_list", "backup_job_create", "backup_job_detail", "backup_job_edit",
    "backup_job_delete", "backup_job_verify",
    "restore_record_list", "restore_record_create", "restore_record_detail", "restore_record_edit",
    "restore_record_delete",
    "data_archive_list", "data_archive_create", "data_archive_detail", "data_archive_edit",
    "data_archive_delete",
    "legal_hold_list", "legal_hold_create", "legal_hold_detail", "legal_hold_edit",
    "legal_hold_delete",
    "environment_instance_list", "environment_instance_create", "environment_instance_detail",
    "environment_instance_edit", "environment_instance_delete",
    "recovery_posture_edit",
    "recovery_drill_list", "recovery_drill_create", "recovery_drill_detail", "recovery_drill_edit",
    "recovery_drill_delete",
]

#: The pages that render on a GET, with the fixture a pk-taking route needs.
LIST_PAGES = [
    ("backup_job_list", None), ("restore_record_list", None), ("data_archive_list", None),
    ("legal_hold_list", None), ("environment_instance_list", None), ("recovery_drill_list", None),
    ("backup_overview", None), ("backup_board", None), ("recovery_posture_edit", None),
]

CREATE_PAGES = [
    ("backup_job_create", None), ("restore_record_create", None), ("data_archive_create", None),
    ("legal_hold_create", None), ("environment_instance_create", None), ("recovery_drill_create", None),
]


# ============================================================ routes

class TestRouteResolution:
    def test_all_34_route_names_reverse(self):
        """A name that does not reverse is a `NoReverseMatch` waiting for the first template that uses
        it. Reversed here without arguments first, then with a pk for the pk-taking ones."""
        reverse_ok, need_pk = [], []
        for name in ROUTE_NAMES:
            try:
                reverse("core:" + name)
                reverse_ok.append(name)
            except NoReverseMatch:
                need_pk.append(name)
        assert len(reverse_ok) + len(need_pk) == 34, "route list drifted from the contract's 34"
        # Every pk-taking route must reverse WITH a pk, or it is broken rather than merely parameterised.
        for name in need_pk:
            assert reverse("core:" + name, args=[1]), name

    def test_the_route_count_matches_the_contract(self):
        from django.urls import get_resolver
        resolver = get_resolver().namespace_dict["core"][1]
        all_names = {str(k) for k in resolver.reverse_dict.keys() if not callable(k)}
        for name in ROUTE_NAMES:
            assert name in all_names, "%s is in the contract but not registered" % name


# ============================================================ GET renders

class TestGetRenders:
    @pytest.mark.parametrize("url_name,_unused", LIST_PAGES)
    def test_list_and_board_pages_render(self, client_a, url_name, _unused):
        response = client_a.get(reverse("core:" + url_name))
        assert response.status_code == 200, url_name

    @pytest.mark.parametrize("url_name,_unused", CREATE_PAGES)
    def test_create_pages_render(self, client_a, url_name, _unused):
        response = client_a.get(reverse("core:" + url_name))
        assert response.status_code == 200, url_name

    @pytest.mark.parametrize("url_name", ["backup_job_detail", "backup_job_edit",
                                          "restore_record_detail", "restore_record_edit",
                                          "data_archive_detail", "data_archive_edit",
                                          "legal_hold_detail", "legal_hold_edit",
                                          "environment_instance_detail", "environment_instance_edit",
                                          "recovery_drill_detail", "recovery_drill_edit"])
    def test_detail_and_edit_pages_render(self, client_a, url_name, request):
        """Each detail/edit page needs its own object; the fixture name is derived from the route so
        adding a route without a fixture fails loudly rather than silently skipping."""
        mapping = {
            "backup_job": "bkp_verified_job_a",
            "restore_record": None,      # built inline below
            "data_archive": "bkp_archive_ok_a",
            "legal_hold": "bkp_hold_active_a",
            "environment_instance": "bkp_env_sandbox_a",
            "recovery_drill": "bkp_drill_a",
        }
        entity = url_name.rsplit("_", 1)[0]
        fixture_name = mapping[entity]
        if fixture_name is None:
            obj = RestoreRecord.objects.create(tenant=request.getfixturevalue("tenant_a"),
                                               scope="full_instance", status="succeeded",
                                               target_time=timezone.now())
        else:
            obj = request.getfixturevalue(fixture_name)
        response = client_a.get(reverse("core:" + url_name, args=[obj.pk]))
        assert response.status_code == 200, url_name

    def test_no_page_leaks_template_syntax(self, client_a, bkp_verified_job_a):
        for url_name in ("backup_overview", "backup_board", "backup_job_list"):
            body = client_a.get(reverse("core:" + url_name)).content.decode()
            leaked = [t for t in ("{%", "{{", "{#") if t in body]
            assert not leaked, "%s leaked %s" % (url_name, leaked)


# ============================================================ the hub's figures

class TestHubZeroRule:
    """C4 and C6 — a green badge is an ACTIVE REASSURANCE and must be earned."""

    def test_empty_workspace_declines_to_reassure(self, client_a):
        """No backups, no archives: both figures are `None` and the page says so."""
        response = client_a.get(reverse("core:backup_overview"))
        ctx = response.context
        body = response.content.decode()
        assert ctx["unverified_count"] is None
        assert ctx["unrestorable_count"] is None
        assert "not applicable" in body
        assert 'badge-green">0<' not in body, "a green 0 is a false all-clear on an empty workspace"

    def test_the_control_a_populated_workspace_still_earns_the_green_zero(self, client_a,
                                                                        bkp_verified_job_a,
                                                                        bkp_archive_ok_a):
        """Without this, the test above would pass if the badge had simply been deleted everywhere —
        and deleting it would be a NEW bug: on a workspace where every backup IS checked, a green `0`
        is exactly the right rendering."""
        response = client_a.get(reverse("core:backup_overview"))
        ctx = response.context
        body = response.content.decode()
        assert ctx["unverified_count"] == 0
        assert ctx["unrestorable_count"] == 0
        assert 'badge-green">0<' in body
        assert "not applicable" not in body

    def test_unverifiable_count_is_None_on_empty(self, client_a):
        """C6 — the claim "all records carry a readable verification state" is about the members of a
        set, and there are no members on an empty workspace.

        **On the BOARD, not the hub**: `unverifiable_count` is a `backup_board` context key. The hub
        has its own pair of zero-rule rows (C4's "Never verified" / "Unrestorable archives") and the
        two pages were fixed separately.
        """
        response = client_a.get(reverse("core:backup_board"))
        assert response.context["unverifiable_count"] is None
        cell = _dd_for(response.content.decode(), "Verification state unreadable")
        assert "not applicable" in cell
        assert "all records carry a readable verification state" not in cell

    def test_unverifiable_count_is_zero_once_a_row_exists(self, client_a, bkp_verified_job_a):
        """The control: with rows present the sentence is TRUE and must still be printed."""
        response = client_a.get(reverse("core:backup_board"))
        assert response.context["unverifiable_count"] == 0
        cell = _dd_for(response.content.decode(), "Verification state unreadable")
        assert "all records carry a readable verification state" in cell

    def test_the_boards_two_zero_rule_rows_agree(self, client_a):
        """C6's actual defect was ONE PAGE, TWO ROWS, TWO ANSWERS: `never_restored` said "not
        applicable" while `unverifiable_count` asserted a clean bill of health about an empty set."""
        body = client_a.get(reverse("core:backup_board")).content.decode()
        for label in ("Successful backups never test-restored", "Verification state unreadable"):
            cell = _dd_for(body, label)
            assert cell is not None and "not applicable" in cell, label

    def test_the_two_sibling_rows_agree_on_an_empty_workspace(self, client_a):
        """C6's actual defect: ONE PAGE, TWO ROWS, TWO ANSWERS to the same question. `never_restored`
        said "not applicable" while `unverifiable_count` asserted a clean bill of health."""
        body = client_a.get(reverse("core:backup_overview")).content.decode()
        for label in ("Never verified", "Unrestorable archives"):
            cell = _dd_for(body, label)
            assert cell is not None and "not applicable" in cell, label
        # And no row on the card prints a green 0.
        assert 'badge-green">0<' not in body


class TestHubInFlightPreview:
    """C8 — the fixer's own Critical: the hub's five-row preview had C5's exact defect."""

    def test_the_queued_backup_is_in_the_preview_and_first(self, client_a, bkp_queued_job_a):
        for index in range(6):
            BackupJob.objects.create(tenant=bkp_queued_job_a.tenant, name="ZZ fin %02d" % index,
                                     status="success",
                                     started_at=timezone.now() - timezone.timedelta(days=index + 1),
                                     integrity_verified_at=timezone.now())
        response = client_a.get(reverse("core:backup_overview"))
        preview = [j.name for j in response.context["recent_jobs"]]
        assert bkp_queued_job_a.name in preview, "an in-flight backup must never be dropped from the preview"
        assert preview[0] == bkp_queued_job_a.name
        assert len(preview) == 5

    def test_the_defect_is_reproducible_with_the_pre_fix_query(self, client_a, bkp_queued_job_a):
        """Reproduce before claiming a fix. The pre-fix query is the model's own `Meta.ordering`,
        sliced to five — `["-started_at", "-id"]` with a NULL `started_at`, which both MariaDB and
        SQLite sort LAST under DESC."""
        for index in range(6):
            BackupJob.objects.create(tenant=bkp_queued_job_a.tenant, name="ZZ fin %02d" % index,
                                     status="success",
                                     started_at=timezone.now() - timezone.timedelta(days=index + 1),
                                     integrity_verified_at=timezone.now())
        pre_fix = [j.name for j in BackupJob.objects.filter(tenant=bkp_queued_job_a.tenant)[:5]]
        assert bkp_queued_job_a.name not in pre_fix, (
            "the premise of C8 is that the pre-fix query OMITS the queued job; if it no longer does, "
            "the ordering assumption has changed and this test is no longer proving anything")


class TestHubQueryCount:
    """I3 — the hub re-derived every count with a second query (measured 20 vs the board's 11)."""

    def test_the_hub_is_in_the_boards_order_of_magnitude(self, client_a, bkp_verified_job_a,
                                                        bkp_archive_ok_a, bkp_env_sandbox_a):
        with CaptureQueriesContext(connection) as hub_ctx:
            client_a.get(reverse("core:backup_overview"))
        with CaptureQueriesContext(connection) as board_ctx:
            client_a.get(reverse("core:backup_board"))
        assert len(hub_ctx.captured_queries) < 20, (
            "the hub was 20 queries before I3; got %d" % len(hub_ctx.captured_queries))
        assert len(hub_ctx.captured_queries) <= len(board_ctx.captured_queries) + 4

    def test_the_figures_still_match_the_database(self, client_a, bkp_verified_job_a,
                                                  bkp_unverified_job_a, bkp_partial_job_a,
                                                  bkp_failed_job_a, bkp_queued_job_a,
                                                  bkp_archive_ok_a, bkp_archive_lost_a):
        """A refactor that reduces queries by computing the WRONG THING would pass the test above."""
        ctx = client_a.get(reverse("core:backup_overview")).context
        tenant = bkp_verified_job_a.tenant
        jobs = list(BackupJob.objects.filter(tenant=tenant))
        archives = list(DataArchive.objects.filter(tenant=tenant))
        settled = [j for j in jobs if not j.is_in_flight]
        assert ctx["job_count"] == len(jobs)
        assert ctx["unverified_count"] == sum(1 for j in settled if j.integrity_verified_at is None)
        assert ctx["unrestorable_count"] == sum(1 for a in archives if not a.is_restorable)
        assert ctx["archive_count"] == len(archives)
        assert ctx["partial_count"] == sum(1 for j in jobs if j.is_partial)
        assert ctx["failed_count"] == sum(1 for j in jobs if j.status == "failed")

    def test_in_flight_rows_are_not_counted_as_unverified(self, client_a, bkp_queued_job_a):
        """A workspace whose ONLY row is queued: nothing has run, so nothing can be unverified. The
        hub must agree with the board, which excludes in-flight rows from `unverified_jobs` for the
        same reason ("naming it would be an accusation rather than a finding")."""
        hub = client_a.get(reverse("core:backup_overview")).context
        board = client_a.get(reverse("core:backup_board")).context
        assert hub["unverified_count"] is None
        assert hub["job_count"] == 1
        assert board["unverified_jobs"] == []


class TestHubTargetsBadge:
    """M6 — the half-set RPO/RTO case."""

    def test_both_set_earns_the_green_set_badge(self, client_a, bkp_posture_both_a):
        body = client_a.get(reverse("core:backup_overview")).content.decode()
        cell = _dd_for(body, "RPO / RTO targets")
        assert 'badge-green">Set<' in cell

    def test_only_one_set_does_NOT_earn_it(self, client_b, bkp_posture_partial_b):
        """M6's whole point: `has_targets` is an `or`, so the half-filled case used to get the same
        green "Set" badge as a workspace carrying both.

        Uses `client_b` because `bkp_posture_partial_b` lives on tenant_b — `RecoveryPosture.tenant` is
        a `OneToOneField`, so the two posture fixtures cannot share a workspace.
        """
        body = client_b.get(reverse("core:backup_overview")).content.decode()
        cell = _dd_for(body, "RPO / RTO targets")
        assert 'badge-green">Set<' not in cell
        assert "Partial" in cell

    def test_neither_set_says_not_set(self, client_a):
        body = client_a.get(reverse("core:backup_overview")).content.decode()
        cell = _dd_for(body, "RPO / RTO targets")
        assert "Not set" in cell
        assert "Partial" not in cell


# ============================================================ the board

class TestBoardInFlight:
    """C5 — the board's ten-row window could not show a backup that was happening."""

    def test_the_queued_job_is_first_with_an_in_flight_note(self, client_a, bkp_queued_job_a):
        ctx = client_a.get(reverse("core:backup_board")).context
        rows = [(r["job"].name, r["note"]) for r in ctx["job_rows"]]
        assert rows, "the board must show at least the queued job"
        assert rows[0][0] == bkp_queued_job_a.name
        assert "Not started yet" in rows[0][1]
        assert "No integrity check recorded" not in rows[0][1], (
            "the old note chain accused a queued backup of a missing check it could not have taken")

    def test_a_running_job_gets_its_own_note(self, client_a, bkp_running_job_a):
        ctx = client_a.get(reverse("core:backup_board")).context
        notes = {r["job"].name: r["note"] for r in ctx["job_rows"]}
        assert "In progress" in notes[bkp_running_job_a.name]

    def test_a_settled_unverified_job_keeps_the_old_note(self, client_a, bkp_unverified_job_a):
        """THE CONTROL: the in-flight branch must not have swallowed the settled case."""
        ctx = client_a.get(reverse("core:backup_board")).context
        notes = {r["job"].name: r["note"] for r in ctx["job_rows"]}
        assert notes[bkp_unverified_job_a.name] == "No integrity check recorded against this backup."

    def test_the_window_still_shows_ten_with_ten_finished_plus_one_queued(self, client_a, bkp_queued_job_a):
        """The measured 9-vs-10 boundary. With ten finished jobs the queued one used to be the row
        that `[:10]` discarded."""
        for index in range(10):
            BackupJob.objects.create(tenant=bkp_queued_job_a.tenant, name="ZZ ten %02d" % index,
                                     status="success",
                                     started_at=timezone.now() - timezone.timedelta(days=index + 1),
                                     integrity_verified_at=timezone.now())
        ctx = client_a.get(reverse("core:backup_board")).context
        names = [r["job"].name for r in ctx["job_rows"]]
        assert bkp_queued_job_a.name in names
        assert len(names) == 10


class TestBoardUnverifiedList:
    def test_in_flight_rows_are_excluded(self, client_a, bkp_queued_job_a, bkp_running_job_a):
        ctx = client_a.get(reverse("core:backup_board")).context
        names = [j.name for j in ctx["unverified_jobs"]]
        assert bkp_queued_job_a.name not in names
        assert bkp_running_job_a.name not in names

    def test_a_cancelled_row_IS_included(self, client_a, bkp_cancelled_job_a):
        """C5's boundary. A cancelled backup has no `started_at`, but it is SETTLED — it has a result
        and its missing check is a real finding. Sweeping it into the in-flight group would hide it."""
        ctx = client_a.get(reverse("core:backup_board")).context
        assert bkp_cancelled_job_a.name in [j.name for j in ctx["unverified_jobs"]]

    def test_a_verified_row_is_excluded(self, client_a, bkp_verified_job_a):
        ctx = client_a.get(reverse("core:backup_board")).context
        assert bkp_verified_job_a.name not in [j.name for j in ctx["unverified_jobs"]]


class TestBoardNeverRestored:
    def test_is_None_when_there_is_no_successful_backup(self, client_a, bkp_failed_job_a):
        ctx = client_a.get(reverse("core:backup_board")).context
        assert ctx["never_restored"] is None

    def test_is_a_figure_when_a_successful_backup_exists(self, client_a, bkp_unverified_job_a):
        ctx = client_a.get(reverse("core:backup_board")).context
        assert ctx["never_restored"] == 1


class TestRetentionBoardHonoursHolds:
    """C2 — a hold must SUSPEND the 0.8 schedule, not merely exist next to it.

    Before the fix the board reported a "due for disposal" figure it could not justify while a
    preservation order was in force: the spoliation the model exists to prevent. The pair of tests
    below is the whole finding — SAME rows, SAME policy, and the only difference is whether an active
    hold covers the scope.
    """

    @staticmethod
    def _seed(tenant, count, age_days=400):
        """A policy pinned to `core.ConsentRecord` plus `count` rows past its window.

        Two details that cost a debugging round each:

        * `ConsentRecord.purpose` is a **FK to `ConsentPurpose`**, not a string — assigning a string
          raises `ValueError: ... must be a "ConsentPurpose" instance`.
        * `created_at` is `auto_now_add`, so the age the board computes cannot be set at insert time;
          the rows are created and then backdated with `update()`. Without that the board reports 0 due
          and the "without a hold" test would pass while proving nothing.
        """
        from apps.core.models import ConsentPurpose, ConsentRecord, Party, RetentionPolicy
        party = Party.objects.create(tenant=tenant, name="Data subject")
        purpose = ConsentPurpose.objects.create(tenant=tenant, name="Marketing",
                                                code="marketing", lawful_basis="consent")
        policy = RetentionPolicy.objects.create(tenant=tenant, name="Consent records",
                                                model_label="core.ConsentRecord",
                                                retention_months=1, action="delete")
        now = timezone.now()
        for index in range(count):
            ConsentRecord.objects.create(tenant=tenant, party=party, purpose=purpose,
                                         action="granted", source="web_form",
                                         occurred_at=now - timezone.timedelta(days=age_days))
        ConsentRecord.objects.filter(tenant=tenant).update(
            created_at=now - timezone.timedelta(days=35))     # past the 30-day window
        return policy

    def test_without_a_hold_the_board_reports_the_rows_as_due(self, client_a, tenant_a):
        """THE PREMISE. Without this the held case below could pass on a board that never reports
        anything due at all."""
        policy = self._seed(tenant_a, 3)
        ctx = client_a.get(reverse("core:retention_board")).context
        row = next(r for r in ctx["rows"] if r["policy"].pk == policy.pk)
        assert row["due"] == 3
        assert row["held_by"] == []

    def test_with_an_active_hold_the_board_names_it_and_reports_no_due(self, client_a, tenant_a):
        policy = self._seed(tenant_a, 3)
        hold = LegalHold.objects.create(tenant=tenant_a, name="Acme v. Initech hold",
                                        retention_policy=policy,
                                        issued_at=timezone.now() - timezone.timedelta(days=5),
                                        status="active")
        response = client_a.get(reverse("core:retention_board"))
        assert response.status_code == 200
        body = response.content.decode()
        row = next(r for r in response.context["rows"] if r["policy"].pk == policy.pk)
        assert row["held_by"], "the policy must be marked as suspended"
        assert row["due"] is None, (
            "a held scope must report NO due figure — reporting one is the false all-clear the "
            "sub-module exists to refuse")
        assert hold.name in body, "the board must NAME the hold, not merely stop counting"
        assert response.context["held_count"] >= 1
        assert hold.name in response.context["held_names"]

    def test_a_released_hold_does_not_suspend(self, client_a, tenant_a):
        """The control: a hold whose release event has happened suspends nothing, so the schedule must
        resume rather than staying suspended forever."""
        policy = self._seed(tenant_a, 3)
        LegalHold.objects.create(tenant=tenant_a, name="Settled hold", retention_policy=policy,
                                 issued_at=timezone.now() - timezone.timedelta(days=40),
                                 status="released",
                                 released_at=timezone.now() - timezone.timedelta(days=1))
        ctx = client_a.get(reverse("core:retention_board")).context
        row = next(r for r in ctx["rows"] if r["policy"].pk == policy.pk)
        assert row["held_by"] == []
        assert row["due"] == 3

    def test_a_hold_on_a_different_scope_does_not_suspend_this_policy(self, client_a, tenant_a):
        """A hold must not suspend scopes it does not cover — otherwise one order would freeze the
        whole workspace and no schedule could ever run."""
        policy = self._seed(tenant_a, 3)
        LegalHold.objects.create(tenant=tenant_a, name="Unrelated hold",
                                 model_label="core.BackupJob",
                                 issued_at=timezone.now() - timezone.timedelta(days=5),
                                 status="active")
        ctx = client_a.get(reverse("core:retention_board")).context
        row = next(r for r in ctx["rows"] if r["policy"].pk == policy.pk)
        assert row["held_by"] == []
        assert row["due"] == 3


# ============================================================ empty states and junk params

class TestEmptyStatesAndJunkParams:
    @pytest.mark.parametrize("url_name", ["backup_job_list", "restore_record_list", "data_archive_list",
                                          "legal_hold_list", "environment_instance_list",
                                          "recovery_drill_list"])
    def test_empty_lists_render_their_empty_state(self, client_a, url_name):
        response = client_a.get(reverse("core:" + url_name))
        assert response.status_code == 200
        assert 'class="empty-state"' in response.content.decode(), url_name

    @pytest.mark.parametrize("url_name,query", [
        ("backup_job_list", "?status=zzz&backup_type=zzz&storage_tier=zzz&integrity=zzz&page=99"),
        ("restore_record_list", "?status=zzz&scope=zzz&page=99"),
        ("data_archive_list", "?status=zzz&storage_tier=zzz&format=zzz&page=99"),
        ("legal_hold_list", "?status=zzz&page=99"),
        ("environment_instance_list", "?kind=zzz&status=zzz&copy_scope=zzz&page=99"),
        ("recovery_drill_list", "?kind=zzz&outcome=zzz&page=99"),
    ])
    def test_junk_filter_values_are_an_empty_200(self, client_a, url_name, query):
        """A junk enum must narrow to nothing, not 500. The `crud_list` junk-enum guard covers the
        values; this covers the page."""
        response = client_a.get(reverse("core:" + url_name) + query)
        assert response.status_code == 200, url_name
        assert list(response.context["object_list"]) == []

    def test_the_boards_render_on_an_empty_workspace(self, client_a):
        for url_name in ("backup_overview", "backup_board"):
            assert client_a.get(reverse("core:" + url_name)).status_code == 200, url_name


# ============================================================ POST verbs

def _round_trip_data(form_class, obj, tenant):
    """Build a valid POST payload from a bound form's own initial values.

    Used for C1: every one of the six edit views must be POSTed a valid payload and asserted to
    redirect AND persist. A GET-only sweep is exactly the blind spot that let C1 ship — the edit pages
    rendered fine and 500'd only on save.
    """
    from django import forms as djforms
    form = form_class(instance=obj, tenant=tenant)
    data = {}
    for name, field in form.fields.items():
        value = form.initial.get(name, "")
        if isinstance(field, djforms.ModelChoiceField):
            # `form.initial` carries the related PK (an int) for a FK, not the instance — so
            # `value.pk` raises `AttributeError: 'int' object has no attribute 'pk'`.
            data[name] = "" if value in (None, "") else (str(value.pk) if hasattr(value, "pk") else str(value))
        elif isinstance(field.widget, djforms.CheckboxInput):
            data[name] = "on" if value else ""
        elif isinstance(field, djforms.DateTimeField) and value:
            data[name] = value.strftime("%Y-%m-%dT%H:%M")
        elif isinstance(field, djforms.DateField) and value:
            data[name] = value.strftime("%Y-%m-%d")
        elif value is None:
            data[name] = ""
        else:
            data[name] = str(value)
    return data


class TestEditViewsPersist:
    """C1 — every one of the six edit views 500'd on a valid save.

    `success_url="core:<entity>_detail"` is a pk-taking route passed as a bare string to `crud_edit`,
    which does `redirect(success_url)`. The row was committed FIRST, so the register diverged from what
    the operator believed they did. This lane POSTs a real payload to each and asserts 302 **plus**
    persistence — the assertion my own GET-only smoke sweep was missing.
    """

    @pytest.mark.parametrize("entity,url_name,fixture_name", [
        ("backup_job", "backup_job_edit", "bkp_verified_job_a"),
        ("data_archive", "data_archive_edit", "bkp_archive_ok_a"),
        ("legal_hold", "legal_hold_edit", "bkp_hold_active_a"),
        ("environment_instance", "environment_instance_edit", "bkp_env_sandbox_a"),
        ("recovery_drill", "recovery_drill_edit", "bkp_drill_a"),
    ])
    def test_edit_view_redirects_and_persists(self, client_a, entity, url_name, fixture_name, request):
        from apps.core import forms as core_forms
        form_class = getattr(core_forms, {
            "backup_job": "BackupJobForm", "data_archive": "DataArchiveForm",
            "legal_hold": "LegalHoldForm", "environment_instance": "EnvironmentInstanceForm",
            "recovery_drill": "RecoveryDrillForm",
        }[entity])
        obj = request.getfixturevalue(fixture_name)
        tenant = request.getfixturevalue("tenant_a")
        data = _round_trip_data(form_class, obj, tenant)
        data["name"] = "Round-tripped %s" % entity
        response = client_a.post(reverse("core:" + url_name, args=[obj.pk]), data)
        assert response.status_code == 302, (
            "%s returned %s, not a redirect — C1's NoReverseMatch would surface here"
            % (url_name, response.status_code))
        obj.refresh_from_db()
        assert obj.name == "Round-tripped %s" % entity, "the redirect happened but the row did not save"

    def test_restore_record_edit_redirects_and_persists(self, client_a, tenant_a, bkp_verified_job_a):
        """`RestoreRecord` is the sixth edit view; its object is built inline because the fixture needs
        a saved source first.

        It must name a **backup or an archive** — the model refuses a restore with no source
        ("a recorded restore with no source cannot be audited"), which the first draft of this test
        discovered by failing validation on an empty payload.
        """
        from apps.core.forms import RestoreRecordForm
        obj = RestoreRecord.objects.create(tenant=tenant_a, backup=bkp_verified_job_a,
                                           scope="full_instance", status="succeeded",
                                           target_time=timezone.now())
        data = _round_trip_data(RestoreRecordForm, obj, tenant_a)
        data["reason"] = "Round-tripped restore"
        response = client_a.post(reverse("core:restore_record_edit", args=[obj.pk]), data)
        assert response.status_code == 302, "form errors: %s" % response.context["form"].errors
        obj.refresh_from_db()
        assert obj.reason == "Round-tripped restore"


class TestVerifyAction:
    """I6 and M1 — the verify action must not assert a check the record denies, and must be
    first-write-wins."""

    def test_verify_a_verified_backup_sets_the_stamp(self, client_a, bkp_unverified_job_a):
        assert bkp_unverified_job_a.integrity_verified_at is None
        response = client_a.post(reverse("core:backup_job_verify", args=[bkp_unverified_job_a.pk]))
        assert response.status_code == 302
        bkp_unverified_job_a.refresh_from_db()
        assert bkp_unverified_job_a.integrity_verified_at is not None

    def test_verify_refuses_a_failed_backup(self, client_a, bkp_failed_job_a):
        """I6: the detail page then showed a green ✓ over a job whose own badge said Failed and whose
        failure reason was "Integrity check failed"."""
        response = client_a.post(reverse("core:backup_job_verify", args=[bkp_failed_job_a.pk]))
        assert response.status_code == 302
        bkp_failed_job_a.refresh_from_db()
        assert bkp_failed_job_a.integrity_verified_at is None, "a failed backup must not be verifiable"

    def test_verify_refuses_a_cancelled_backup(self, client_a, bkp_cancelled_job_a):
        client_a.post(reverse("core:backup_job_verify", args=[bkp_cancelled_job_a.pk]))
        bkp_cancelled_job_a.refresh_from_db()
        assert bkp_cancelled_job_a.integrity_verified_at is None

    def test_verify_records_the_method_alongside_the_stamp(self, client_a, bkp_unverified_job_a):
        """A stamp with no method is half a record — the verify action sets both."""
        assert bkp_unverified_job_a.integrity_method == "none"
        client_a.post(reverse("core:backup_job_verify", args=[bkp_unverified_job_a.pk]))
        bkp_unverified_job_a.refresh_from_db()
        assert bkp_unverified_job_a.integrity_verified_at is not None
        assert bkp_unverified_job_a.integrity_method != "none"

    # NOTE: `L5-M1` (lane 5) also noted that a second verify silently RE-DATES the stamp. That finding
    # was **not carried into the consolidated 12 Minor list**, so the fixer was never asked to change
    # it and the behaviour stands: re-verifying updates `integrity_verified_at` to the later time.
    # No test asserts either way here. It is flagged in the review file rather than silently enforced —
    # "last verified" is a defensible reading of a single nullable column, and there is no field for a
    # verification history, so first-write-wins would lose the more recent check instead.

    def test_the_page_never_shows_a_green_tick_over_a_failed_job(self, client_a, bkp_failed_job_a):
        """The assertion that ties I6 to what the operator actually sees."""
        client_a.post(reverse("core:backup_job_verify", args=[bkp_failed_job_a.pk]))
        body = client_a.get(reverse("core:backup_job_detail", args=[bkp_failed_job_a.pk])).content.decode()
        assert "Verified" not in body or "text-ok" not in body


class TestHoldReleaseSameMinute:
    """I7 through the view."""

    def test_release_in_the_same_minute_as_issue_is_accepted(self, client_a, bkp_hold_active_a):
        data = {"name": bkp_hold_active_a.name, "custodian": "", "subject_party": "",
                "matter_reference": "", "issuing_authority": "", "scope": "",
                "retention_policy": "", "model_label": "", "status": "released",
                "released_at": bkp_hold_active_a.issued_at.strftime("%Y-%m-%dT%H:%M"),
                "release_reason": "Wrong hold.", "authority_reference": "", "notes": ""}
        response = client_a.post(reverse("core:legal_hold_edit", args=[bkp_hold_active_a.pk]), data)
        assert response.status_code == 302
        bkp_hold_active_a.refresh_from_db()
        assert bkp_hold_active_a.status == "released"


def _dd_for(body, label):
    """The `<dd>` belonging to a given `<dt>`, so an assertion cannot be satisfied by a sibling row."""
    found = re.search(r"<dt>%s</dt>\s*<dd>(.*?)</dd>" % re.escape(label), body, re.S)
    return found.group(1) if found else None
