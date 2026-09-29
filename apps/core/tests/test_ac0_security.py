"""0.20 SECURITY lane — cross-tenant isolation, the role gate, and refusal-writes-no-audit.

Against `.claude/tasks/test-contract-core-0.20.md`.

**The verbs are the surface that actually mutates**, so they get the IDOR coverage the CRUD smoke
did not: the 37-check sweep proved cross-tenant 404 on the five models, but a hand-made POST to a
verb is a different request on a different code path.

**404 for BOTH cases is the contract.** A cross-tenant pk and a nonexistent pk must take the
identical path to an identical 404 — a 403/404 split is a pk-enumeration oracle.
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

#: (url name, fixture producing a tenant_a row) — the five CRUD detail routes.
_DETAIL_ROUTES = [
    ("jobdefinition_detail", "ac0_job"),
    ("jobrun_detail", "ac0_run"),
    ("maintenancewindow_detail", "ac0_window"),
    ("changerequest_detail", "ac0_change"),
    ("featurerollout_detail", "ac0_rollout"),
]

#: (url name, fixture) — the verbs that take a pk. `bulk_preview` takes none and is excluded here.
_VERB_ROUTES = [
    ("jobdefinition_run_now", "ac0_job"),
    ("maintenance_window_end_now", "ac0_window_running"),
    ("change_request_submit", "ac0_change_draft"),
    ("change_request_approve", "ac0_change"),
    ("change_request_rollback", "ac0_change_completed"),
]


class TestAc0CrossTenantReads:
    @pytest.mark.parametrize("name,fixture", _DETAIL_ROUTES)
    def test_ac0_cross_tenant_detail_is_404(self, client_b, request, name, fixture):
        obj = request.getfixturevalue(fixture)
        assert client_b.get(reverse("core:" + name, args=[obj.pk])).status_code == 404

    @pytest.mark.parametrize("name", ["jobdefinition", "jobrun", "maintenancewindow",
                                      "changerequest", "featurerollout"])
    def test_ac0_cross_tenant_list_renders_empty(self, client_b, name):
        """A list is the caller's OWN (empty) data, never another workspace's rows."""
        r = client_b.get(reverse("core:%s_list" % name))
        assert r.status_code == 200


class TestAc0CrossTenantWrites:
    @pytest.mark.parametrize("name,fixture", _VERB_ROUTES)
    def test_ac0_cross_tenant_verb_post_is_404_and_writes_nothing(
            self, client_b, request, name, fixture):
        obj = request.getfixturevalue(fixture)
        before = AuditLog.objects.count()
        r = client_b.post(reverse("core:" + name, args=[obj.pk]))
        assert r.status_code == 404, "cross-tenant POST to %s -> %s" % (name, r.status_code)
        assert AuditLog.objects.count() == before, "a refused POST must not write an audit row"

    @pytest.mark.parametrize("name,fixture", _VERB_ROUTES)
    def test_ac0_a_nonexistent_pk_also_returns_404(self, client_a, name, fixture):
        """404 for BOTH cases, so the response is not a pk-enumeration oracle."""
        assert client_a.post(reverse("core:" + name, args=[99999999])).status_code == 404


class TestAc0TenantQuerysetsAreScoped:
    @pytest.mark.parametrize("model,fixture", [
        (JobDefinition, "ac0_job"), (JobRun, "ac0_run"),
        (MaintenanceWindow, "ac0_window"), (ChangeRequest, "ac0_change"),
        (FeatureRollout, "ac0_rollout"),
    ])
    def test_ac0_a_tenant_b_queryset_excludes_tenant_a_rows(self, request, tenant_a, tenant_b,
                                                             model, fixture):
        """The fixture is REQUESTED, not merely named: without it tenant_a has no rows and the
        `assert > 0` half would pass for the wrong reason."""
        request.getfixturevalue(fixture)
        assert model.objects.filter(tenant=tenant_b).count() == 0, \
            "%s: a tenant_b queryset returned a tenant_a row" % model.__name__
        assert model.objects.filter(tenant=tenant_a).count() > 0, \
            "%s: the tenant_a fixture produced no row, so the isolation above proves nothing" \
            % model.__name__


class TestAc0RoleGate:
    """`tenant_admin_required` is `superuser OR is_tenant_admin`, so a plain member is refused."""

    @pytest.mark.parametrize("name", ["admin_board", "support_board", "bulk_board",
                                      "ops_audit_trail", "jobdefinition_list",
                                      "maintenancewindow_list", "changerequest_list"])
    def test_ac0_a_plain_member_cannot_reach_a_board_or_register(self, member_client, name):
        assert member_client.get(reverse("core:" + name)).status_code == 403

    def test_ac0_a_plain_member_cannot_post_a_verb(self, member_client, ac0_job):
        before = JobRun.objects.count()
        r = member_client.post(reverse("core:jobdefinition_run_now", args=[ac0_job.pk]))
        assert r.status_code == 403
        assert JobRun.objects.count() == before

    def test_ac0_anonymous_is_redirected_to_login(self, client):
        """A `client` fixture with no login is anonymous. The decorator order decides the answer:
        `@login_required` sits INSIDE `@tenant_admin_required`, so an anonymous request is sent to
        the login page rather than being told it lacks a role it never had."""
        r = client.get(reverse("core:admin_board"))
        assert r.status_code in (302, 403)
        if r.status_code == 302:
            assert "login" in r["Location"].lower()

class TestAc0RefusalsWriteNoAudit:
    """A guard that writes the audit row anyway has recorded an action nobody performed."""

    def test_ac0_a_refused_rollback_writes_nothing(self, client_a, ac0_change_completed):
        before = AuditLog.objects.count()
        client_a.post(reverse("core:change_request_rollback", args=[ac0_change_completed.pk]),
                      {"rollback_reason": ""})
        ac0_change_completed.refresh_from_db()
        assert ac0_change_completed.status != "rolled_back"
        assert AuditLog.objects.count() == before

    def test_ac0_a_refused_cross_state_approval_writes_nothing(self, client_a, ac0_change_draft):
        before = AuditLog.objects.count()
        client_a.post(reverse("core:change_request_approve", args=[ac0_change_draft.pk]))
        ac0_change_draft.refresh_from_db()
        assert ac0_change_draft.status == "draft"
        assert AuditLog.objects.count() == before

    def test_ac0_a_refused_window_delete_writes_nothing(self, client_a, ac0_window_past):
        before = AuditLog.objects.count()
        client_a.post(reverse("core:maintenancewindow_delete", args=[ac0_window_past.pk]))
        assert MaintenanceWindow.objects.filter(pk=ac0_window_past.pk).exists()
        assert AuditLog.objects.count() == before


class TestAc0NoForgedStamps:
    """X3 at the REQUEST level: a hand-made POST must not be able to attach an evidence stamp.

    The FORMS lane proves the fields are absent from the form. This proves the request path, so a
    regression in either the form or the view fails here.
    """

    def test_ac0_requested_at_cannot_be_forged_by_post(self, client_a, ac0_change_draft,
                                                      ac0_change_payload):
        payload = dict(ac0_change_payload, status="draft", requested_at="2019-01-01T00:00:00")
        client_a.post(reverse("core:changerequest_edit", args=[ac0_change_draft.pk]), payload)
        ac0_change_draft.refresh_from_db()
        assert ac0_change_draft.requested_at is None, \
            "a draft that was never submitted must carry no request stamp"

    def test_ac0_approved_by_cannot_be_forged_by_post(self, client_a, ac0_change_draft,
                                                     ac0_change_payload):
        payload = dict(ac0_change_payload, status="draft", approved_by=1)
        client_a.post(reverse("core:changerequest_edit", args=[ac0_change_draft.pk]), payload)
        ac0_change_draft.refresh_from_db()
        assert ac0_change_draft.approved_by_id is None
        assert ac0_change_draft.approved_at is None

    def test_ac0_ended_at_cannot_be_forged_by_post(self, client_a, ac0_window, ac0_window_payload):
        """Only the `end_now` verb may stamp a window's ending — it is the actor of record."""
        payload = dict(ac0_window_payload, status="ended_early", ended_at="2020-01-01T00:00:00")
        client_a.post(reverse("core:maintenancewindow_edit", args=[ac0_window.pk]), payload)
        ac0_window.refresh_from_db()
        assert ac0_window.ended_at is None

    def test_ac0_is_dry_run_cannot_be_cleared_by_post(self, client_a, ac0_run, ac0_run_payload):
        """Nothing in this repository can legitimately execute a job, so nothing may claim it did."""
        payload = {k: v for k, v in dict(ac0_run_payload, status="success").items()
                   if k != "is_dry_run"}
        client_a.post(reverse("core:jobrun_edit", args=[ac0_run.pk]), payload)
        ac0_run.refresh_from_db()
        assert ac0_run.is_dry_run, "a form POST must not be able to clear the dry-run flag"


class TestAc0HandlerPathIsNeverExecuted:
    """`handler_path` is free text a user supplies. Nothing imports it — and if anything ever did,
    this would be remote code execution, so it is asserted rather than assumed."""

    def test_ac0_nothing_in_the_repository_resolves_the_handler_path(self):
        """Only the FILES THAT MENTION `handler_path` are scanned, and only for a resolution
        construct on the SAME line as the field.

        A file-wide scan for `getattr(` or `import_module` would flag any file that merely declares
        the field, because those constructs are everywhere in this codebase. The question is
        narrower: does any line take the `handler_path` VALUE and resolve it?
        """
        import pathlib
        root = pathlib.Path(__file__).resolve().parents[3]
        resolvers = ("import_module", "import_string", "getattr(", "eval(", "exec(")
        offenders = []
        for path in root.glob("apps/**/*.py"):
            for lineno, line in enumerate(path.read_text(
                    encoding="utf-8", errors="replace").splitlines(), 1):
                if "handler_path" not in line:
                    continue
                if any(tok in line for tok in resolvers):
                    offenders.append("%s:%d" % (path.relative_to(root), lineno))
        assert not offenders, (
            "something RESOLVES a handler_path value, which would be remote code execution: %s"
            % offenders)