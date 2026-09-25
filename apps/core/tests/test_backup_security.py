"""0.16 security-lane tests — Backup, Recovery & Data Lifecycle.

Contract: `.claude/tasks/test-contract-core-0.16.md` §7.

The theme: **this sub-module records events that only a person can attest to** — a backup taken, a
restore performed, a hold released — so the register is only as trustworthy as its isolation. A page
that lets one workspace read or write another's rows does not merely leak; it makes every row it shows
unusable as evidence.

The lane also pins the C7 escalation from the security side, because the live leak that was found
(and fixed) was a *security* defect, not a scoping preference.
"""
import os
import re

import pytest
from django.contrib.auth import get_user_model
from django.test import Client
from django.urls import reverse
from django.utils import timezone

from apps.core.models import BackupJob, DataArchive, EnvironmentInstance, RecoveryDrill, RestoreRecord
from apps.core.models.LegalHold import LegalHold

User = get_user_model()

#: The seven POST-only verbs. `@require_POST` sits ABOVE the role gate on all of them, per 7.7's ruling
#: — decorators apply bottom-up, so the outermost runs first and a wrong method must yield **405**
#: regardless of the caller's role, never 403.
POST_ONLY = [
    "backup_job_verify", "backup_job_delete", "restore_record_delete", "data_archive_delete",
    "legal_hold_delete", "environment_instance_delete", "recovery_drill_delete",
]

#: Routes that take a pk, with the fixture supplying tenant_a's object and the tenant_b object whose pk
#: must 404. The tenant_b fixture is resolved by name so a missing one fails loudly.
IDOR_ROUTES = [
    ("backup_job_detail", "bkp_verified_job_a", "bkp_job_b"),
    ("backup_job_edit", "bkp_verified_job_a", "bkp_job_b"),
    ("data_archive_detail", "bkp_archive_ok_a", "bkp_archive_b"),
    ("data_archive_edit", "bkp_archive_ok_a", "bkp_archive_b"),
    ("legal_hold_detail", "bkp_hold_active_a", "bkp_hold_b"),
    ("legal_hold_edit", "bkp_hold_active_a", "bkp_hold_b"),
    ("environment_instance_detail", "bkp_env_sandbox_a", "bkp_env_b"),
    ("environment_instance_edit", "bkp_env_sandbox_a", "bkp_env_b"),
    ("recovery_drill_detail", "bkp_drill_a", "bkp_drill_b"),
    ("recovery_drill_edit", "bkp_drill_a", "bkp_drill_b"),
]

ALL_GET_ROUTES = [
    "backup_overview", "backup_board",
    "backup_job_list", "backup_job_create", "restore_record_list", "restore_record_create",
    "data_archive_list", "data_archive_create", "legal_hold_list", "legal_hold_create",
    "environment_instance_list", "environment_instance_create", "recovery_drill_list",
    "recovery_drill_create", "recovery_posture_edit",
]


# ============================================================ anonymous

class TestAnonymousAccess:
    @pytest.mark.parametrize("url_name", ALL_GET_ROUTES)
    def test_anonymous_is_redirected(self, client, db, url_name):
        response = client.get(reverse("core:" + url_name))
        assert response.status_code == 302, url_name
        assert "/login" in response["Location"] or "accounts" in response["Location"], url_name

    @pytest.mark.parametrize("url_name", POST_ONLY)
    def test_anonymous_is_refused_on_post_only_verbs(self, client, db, url_name):
        """405 or 302 — either way NOT 200, and never a 500."""
        response = client.post(reverse("core:" + url_name, args=[1]))
        assert response.status_code in (302, 405), "%s -> %s" % (url_name, response.status_code)


# ============================================================ role gate

class TestRoleGate:
    @pytest.mark.parametrize("url_name", ALL_GET_ROUTES)
    def test_a_non_admin_member_is_refused(self, member_client, url_name):
        response = member_client.get(reverse("core:" + url_name))
        assert response.status_code == 403, "%s -> %s" % (url_name, response.status_code)

    def test_the_admin_is_allowed(self, client_a):
        assert client_a.get(reverse("core:backup_overview")).status_code == 200


class TestWrongMethodIs405RegardlessOfRole:
    """7.7's ruling: the method check runs BEFORE the role check, so a GET on a POST-only verb is
    **405** for everyone. A 403 would be wrong — it would tell a member they lack a role when the real
    problem is that they used the wrong verb, and it would tell an ADMIN the same thing.
    """

    @pytest.mark.parametrize("url_name", POST_ONLY)
    def test_get_on_a_post_only_verb_is_405_for_the_admin(self, client_a, url_name):
        response = client_a.get(reverse("core:" + url_name, args=[1]))
        assert response.status_code == 405, "%s -> %s" % (url_name, response.status_code)

    @pytest.mark.parametrize("url_name", POST_ONLY)
    def test_get_on_a_post_only_verb_is_405_for_a_member_too(self, member_client, url_name):
        """The whole point of the ordering: the member must see 405, not 403."""
        response = member_client.get(reverse("core:" + url_name, args=[1]))
        assert response.status_code == 405, "%s -> %s" % (url_name, response.status_code)


# ============================================================ cross-tenant

class TestCrossTenantIsolation:
    @pytest.mark.parametrize("url_name,own_fixture,foreign_fixture", IDOR_ROUTES)
    def test_a_foreign_pk_is_404(self, client_a, request, url_name, own_fixture, foreign_fixture):
        foreign = request.getfixturevalue(foreign_fixture)
        response = client_a.get(reverse("core:" + url_name, args=[foreign.pk]))
        assert response.status_code == 404, (
            "%s returned %s for another tenant's pk" % (url_name, response.status_code))

    @pytest.mark.parametrize("url_name,own_fixture,foreign_fixture", IDOR_ROUTES)
    def test_the_owners_own_pk_still_works(self, client_a, request, url_name, own_fixture, foreign_fixture):
        """THE CONTROL — without it the 404s above would pass on a page that 404s everything."""
        own = request.getfixturevalue(own_fixture)
        response = client_a.get(reverse("core:" + url_name, args=[own.pk]))
        assert response.status_code == 200, url_name

    def test_a_foreign_pk_is_404_on_the_delete_verbs(self, client_a, bkp_job_b, bkp_archive_b,
                                                     bkp_hold_b, bkp_env_b, bkp_drill_b):
        """DELETE is the verb where a missing tenant filter is destructive rather than merely leaky."""
        for url_name, foreign in (("backup_job_delete", bkp_job_b),
                                  ("data_archive_delete", bkp_archive_b),
                                  ("legal_hold_delete", bkp_hold_b),
                                  ("environment_instance_delete", bkp_env_b),
                                  ("recovery_drill_delete", bkp_drill_b)):
            response = client_a.post(reverse("core:" + url_name, args=[foreign.pk]))
            assert response.status_code == 404, "%s -> %s" % (url_name, response.status_code)
            assert foreign.__class__.objects.filter(pk=foreign.pk).exists(), (
                "%s deleted another tenant's row" % url_name)

    def test_no_list_page_names_another_tenants_row(self, client_a, bkp_job_b, bkp_archive_b,
                                                    bkp_hold_b, bkp_env_b, bkp_drill_b):
        for url_name in ("backup_job_list", "data_archive_list", "legal_hold_list",
                         "environment_instance_list", "recovery_drill_list"):
            body = client_a.get(reverse("core:" + url_name)).content.decode()
            for foreign in (bkp_job_b, bkp_archive_b, bkp_hold_b, bkp_env_b, bkp_drill_b):
                assert foreign.name not in body, "%s leaked %r" % (url_name, foreign.name)


# ============================================================ mass assignment

class TestMassAssignment:
    def test_posting_a_tenant_is_ignored(self, client_a, tenant_a, tenant_b, bkp_job_payload):
        """`tenant` is never a form field, so a crafted POST cannot place a row in another workspace.
        The view sets it from `request.tenant`."""
        bkp_job_payload["tenant"] = str(tenant_b.pk)
        response = client_a.post(reverse("core:backup_job_create"), bkp_job_payload)
        assert response.status_code == 302, response.context["form"].errors
        created = BackupJob.objects.get(name=bkp_job_payload["name"])
        assert created.tenant_id == tenant_a.pk

    def test_posting_a_foreign_fk_is_refused(self, client_a, bkp_key_b, bkp_job_payload):
        """A hand-posted foreign pk must be refused — by the narrowed queryset and, at the model edge,
        by `TenantConsistentMixin` (I2), which is what covers the admin too."""
        bkp_job_payload["encryption_key"] = str(bkp_key_b.pk)
        response = client_a.post(reverse("core:backup_job_create"), bkp_job_payload)
        assert response.status_code == 200
        assert "encryption_key" in response.context["form"].errors
        assert not BackupJob.objects.filter(name=bkp_job_payload["name"]).exists()

    def test_the_actor_fields_cannot_be_forged(self, client_a, tenant_a, bkp_job_payload):
        """`performed_by` is not a form field: the actor is the request user. A forged value would let
        somebody attribute a backup to a colleague."""
        other = User.objects.create_user(username="other_acme", email="other@acme.test",
                                        tenant=tenant_a, is_tenant_admin=True)
        bkp_job_payload["performed_by"] = str(other.pk)
        response = client_a.post(reverse("core:backup_job_create"), bkp_job_payload)
        assert response.status_code == 302, response.context["form"].errors
        created = BackupJob.objects.get(name=bkp_job_payload["name"])
        assert created.performed_by_id != other.pk


# ============================================================ the tenant-less actor

class TestTenantLessActor:
    """The superuser `admin` has `tenant=None` **by design**. Every 0.16 page must either send them away
    or show them NOTHING — and must never 500, and never fall back to "all tenants".

    The two halves behave differently, and the difference is safe but worth pinning:

    * the **boards, the hub and the create pages** guard explicitly (`request.tenant is None` ->
      message + redirect to the dashboard);
    * the **six list pages** do not guard — they run `filter(tenant=None)`, which matches rows whose
      `tenant_id IS NULL`, of which there are none, so they render **200 with an empty list**.

    Neither leaks. The list behaviour is the weaker of the two (a superuser sees a working page that is
    silently empty rather than being told why), but it is not a security defect and changing it is not
    in this sub-module's findings — so the tests assert the property that MATTERS (zero rows) on both,
    and record the inconsistency rather than quietly encoding one of the two as "correct".
    """

    @pytest.fixture
    def superuser_client(self, db):
        user = User.objects.create_superuser(username="zz_super", email="zz_super@example.test",
                                             password="TestPass123!", tenant=None)
        client = Client()
        client.force_login(user)
        return client

    REDIRECTING_ROUTES = ["backup_overview", "backup_board", "backup_job_create",
                          "restore_record_create", "data_archive_create", "legal_hold_create",
                          "environment_instance_create", "recovery_drill_create",
                          "recovery_posture_edit"]

    LIST_ROUTES = ["backup_job_list", "restore_record_list", "data_archive_list",
                   "legal_hold_list", "environment_instance_list", "recovery_drill_list"]

    @pytest.mark.parametrize("url_name", REDIRECTING_ROUTES)
    def test_the_guarded_pages_redirect_the_tenant_less_actor(self, superuser_client, url_name):
        response = superuser_client.get(reverse("core:" + url_name))
        assert response.status_code == 302, "%s -> %s" % (url_name, response.status_code)
        assert reverse("dashboard:home") in response["Location"]

    @pytest.mark.parametrize("url_name", LIST_ROUTES)
    def test_the_list_pages_show_a_tenant_less_actor_nothing(self, superuser_client, url_name,
                                                            bkp_job_b, bkp_archive_b, bkp_hold_b,
                                                            bkp_env_b, bkp_drill_b):
        """The security property: **zero rows**, even though other tenants' rows exist. A 200 is
        acceptable here precisely because the list is empty — the leak would be a populated one."""
        response = superuser_client.get(reverse("core:" + url_name))
        assert response.status_code in (200, 302), "%s -> %s" % (url_name, response.status_code)
        if response.status_code == 200:
            assert list(response.context["object_list"]) == [], (
                "%s showed a tenant-less actor %d row(s)"
                % (url_name, len(list(response.context["object_list"]))))

    def test_no_route_500s_for_a_tenant_less_actor(self, superuser_client):
        """The blanket assertion: every GET route must survive. A 500 is the failure mode that matters
        most here, because it is what a missing guard looks like when it is not merely cosmetic."""
        for url_name in self.REDIRECTING_ROUTES + self.LIST_ROUTES:
            response = superuser_client.get(reverse("core:" + url_name))
            assert response.status_code != 500, "%s 500'd" % url_name


# ============================================================ C7 — the live leak that was fixed

class TestConnectorFormDoesNotLeakUsers:
    """C7's probe found this LIVE in `apps/projects`, and it is a security finding, so it is asserted
    from the security lane.

    `ProjectIntegrationConnectorForm.__init__` built `User.objects.filter(is_active=True)` and applied
    the tenant filter only `if self.tenant is not None`, so a tenant-less form offered EVERY workspace's
    active users. `User.__str__` returns the email, so the `<select>` rendered other tenants' addresses
    — and `ixc_create` carries only `@login_required`, so the superuser reached it.

    The base-class half of C7 was reverted (it broke 15 tests across three modules); **this** half is
    self-sufficient and stays.
    """

    def test_a_tenant_less_connector_form_offers_no_users(self, db, bkp_key_a):
        from apps.projects.forms.IntegrationApiHub.Connectors import ProjectIntegrationConnectorForm
        form = ProjectIntegrationConnectorForm(tenant=None)
        assert form.fields["owner"].queryset.count() == 0
        labels = [str(label) for _value, label in form.fields["owner"].choices]
        assert labels == ["---------"], "only the blank choice may remain; got %s" % labels

    def test_the_scoped_connector_form_still_works(self, tenant_a, admin_user):
        """THE CONTROL — the fix must not have emptied the dropdown on the real path."""
        from apps.projects.forms.IntegrationApiHub.Connectors import ProjectIntegrationConnectorForm
        form = ProjectIntegrationConnectorForm(tenant=tenant_a)
        pks = set(form.fields["owner"].queryset.values_list("pk", flat=True))
        assert admin_user.pk in pks

    def test_no_other_tenants_email_appears_in_the_choices(self, db, tenant_a, tenant_b):
        """Asserted by VALUE, not by count: the leak rendered emails, so the check names them."""
        from apps.projects.forms.IntegrationApiHub.Connectors import ProjectIntegrationConnectorForm
        other = User.objects.create_user(username="zz_globex_owner",
                                        email="zz-globex-owner@example.test",
                                        tenant=tenant_b, is_tenant_admin=True)
        form = ProjectIntegrationConnectorForm(tenant=None)
        labels = " ".join(str(label) for _value, label in form.fields["owner"].choices)
        assert other.email not in labels


# ============================================================ XSS

class TestEscaping:
    def test_a_script_tag_in_a_name_is_escaped_in_the_list(self, client_a, tenant_a):
        BackupJob.objects.create(tenant=tenant_a, name="<script>alert('xss')</script>",
                                 status="success", started_at=timezone.now())
        body = client_a.get(reverse("core:backup_job_list")).content.decode()
        assert "<script>alert('xss')</script>" not in body
        assert "&lt;script&gt;" in body

    def test_a_script_tag_in_a_hold_name_is_escaped_on_the_board(self, client_a, tenant_a):
        LegalHold.objects.create(tenant=tenant_a, name="<script>alert('xss')</script>",
                                 issued_at=timezone.now(), status="active")
        body = client_a.get(reverse("core:backup_board")).content.decode()
        assert "<script>alert('xss')</script>" not in body

    def test_a_script_tag_in_a_job_name_is_escaped_on_the_hub(self, client_a, tenant_a):
        BackupJob.objects.create(tenant=tenant_a, name="<script>alert('xss')</script>",
                                 status="success", started_at=timezone.now())
        body = client_a.get(reverse("core:backup_overview")).content.decode()
        assert "<script>alert('xss')</script>" not in body

    def test_no_0_16_template_interpolates_user_text_into_onsubmit(self):
        """L42's shape, third recurrence repo-wide: HTML escaping does NOT protect an inline-handler
        attribute, so user text inside `onsubmit="…"` needs `|escapejs`.

        Scanned from SOURCE rather than by rendering, because the dangerous case is a template that
        *would* interpolate a value — one a rendered page might never reach.
        """
        offenders = []
        for root, _dirs, files in os.walk("templates/core"):
            for filename in files:
                if not filename.endswith(".html"):
                    continue
                path = os.path.join(root, filename)
                with open(path, encoding="utf-8") as handle:
                    text = handle.read()
                for match in re.finditer(r'onsubmit="[^"]*"', text):
                    handler = match.group(0)
                    # A `{{ … }}` inside the handler is the risk; a literal confirm() is not.
                    if "{{" in handler and "escapejs" not in handler:
                        offenders.append("%s: %s" % (path, handler[:90]))
        assert not offenders, "user text interpolated into onsubmit without |escapejs: %s" % offenders

    def test_the_0_16_delete_confirms_are_static_strings(self):
        """The complement of the test above: the delete `onsubmit`s are literal text, which is safe.
        Pinned so a change that starts interpolating a name into one is caught."""
        checked = 0
        for root, _dirs, files in os.walk("templates/core"):
            for filename in files:
                if not filename.endswith(".html"):
                    continue
                with open(os.path.join(root, filename), encoding="utf-8") as handle:
                    text = handle.read()
                for match in re.finditer(r'onsubmit="([^"]*)"', text):
                    handler = match.group(1)
                    if "confirm(" in handler:
                        checked += 1
                        assert "{{" not in handler, "%s interpolates into onsubmit" % filename
        assert checked > 0, "expected at least one static confirm() in templates/core"
