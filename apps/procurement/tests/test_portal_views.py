"""Procurement 6.1 - view flows.

Every surface is exercised through the rendered BYTES (``response.context`` is ``None`` without
``setup_test_environment()`` and an assertion against it passes trivially). The quick-requisition
hand-off is the load-bearing flow: the portal must draft INTO scm's requisition spine (L36) under
the signed-in user's name with a derived total, never a client-supplied one.
"""
import datetime

import pytest
from django.urls import reverse
from django.utils import timezone

from apps.core.models import AuditLog
from apps.procurement.models import ProcurementAlert, WidgetPreference
from apps.scm.models import PurchaseRequisition

pytestmark = pytest.mark.django_db


def _pr_count(tenant):
    return PurchaseRequisition.objects.filter(tenant=tenant).count()


# ------------------------------------------------------------------ pages render


class TestPagesRender:
    def test_dashboard_renders_stats_and_quick_links(self, client_a, alert_open):
        resp = client_a.get(reverse("procurement:dashboard"))
        assert resp.status_code == 200
        body = resp.content.decode()
        assert "Procurement Portal" in body
        assert alert_open.title in body  # my-open-alerts widget shows assigned work

    def test_alert_list_renders_and_searches(self, client_a, alert_open):
        url = reverse("procurement:alert_list")
        assert client_a.get(url).status_code == 200
        hit = client_a.get(url, {"q": "Printer paper"})
        assert alert_open.title.encode() in hit.content
        miss = client_a.get(url, {"q": "wombat"})
        assert b"No alerts match" in miss.content

    def test_alert_filters_narrow(self, client_a, alert_open, alert_resolved):
        url = reverse("procurement:alert_list")
        only_open = client_a.get(url, {"status": "open"})
        assert alert_open.title.encode() in only_open.content
        assert alert_resolved.title.encode() not in only_open.content

    def test_quickreq_get_lists_recent_entries(self, client_a, tenant_a, admin_user):
        PurchaseRequisition.objects.create(tenant=tenant_a, title="Earlier entry",
                                           requester=admin_user)
        resp = client_a.get(reverse("procurement:quickreq_create"))
        assert resp.status_code == 200
        assert b"Earlier entry" in resp.content

    def test_reports_page_renders_tables(self, client_a):
        resp = client_a.get(reverse("procurement:report_index"))
        assert resp.status_code == 200
        body = resp.content.decode()
        assert "My Requisitions by Status" in body
        assert "Committed Spend by Month" in body

    def test_report_export_csv(self, client_a, tenant_a, admin_user):
        PurchaseRequisition.objects.create(tenant=tenant_a, title="CSV row",
                                           requester=admin_user)
        resp = client_a.get(reverse("procurement:report_export"))
        assert resp.status_code == 200
        assert resp["Content-Type"] == "text/csv"
        assert "attachment" in resp["Content-Disposition"]
        assert b"CSV row" in resp.content


# ------------------------------------------------------------------ widget toggle


class TestWidgetToggle:
    def test_post_persists_choices_and_hides_sections(self, client_a, tenant_a, admin_user):
        WidgetPreference.objects.filter(tenant=tenant_a, user=admin_user).delete()
        resp = client_a.post(reverse("procurement:dashboard"),
                             {"widgets": ["approvals", "spend"]})
        assert resp.status_code == 302
        assert WidgetPreference.hidden_keys(tenant_a, admin_user) == {
            "alerts", "deadlines", "activity"}
        page = client_a.get(reverse("procurement:dashboard")).content.decode()
        assert "Pending Approvals" in page            # kept
        assert "Assigned to Me" not in page           # hidden section gone entirely

    def test_default_is_all_visible_without_rows(self, client_a, tenant_a, admin_user):
        WidgetPreference.objects.filter(tenant=tenant_a, user=admin_user).delete()
        page = client_a.get(reverse("procurement:dashboard")).content.decode()
        for label in ("Pending Approvals", "Assigned to Me", "Spend Summary",
                      "Approaching Deadlines", "Recent Activity"):
            assert label in page


# ------------------------------------------------------------------ quick requisition


class TestQuickRequisitionFlow:
    def _post(self, client, gl=None, org=None, **overrides):
        data = {"title": "Smoke quick req", "item_description": "Toner cartridge",
                "quantity": "2", "estimated_unit_price": "49.90", "uom_hint": "each",
                "sku_hint": "", "currency": "", "gl_account": gl.pk if gl else "",
                "org_unit": org.pk if org else "", "required_by": "2026-09-15",
                "justification": "test"}
        data.update(overrides)
        return client.post(reverse("procurement:quickreq_create"), data)

    def test_creates_single_line_pr_on_the_scm_spine(self, client_a, tenant_a,
                                                     admin_user, gl_expense_a, org_unit_a):
        before = _pr_count(tenant_a)
        resp = self._post(client_a, gl_expense_a, org_unit_a)
        assert resp.status_code == 302
        assert _pr_count(tenant_a) == before + 1
        pr = PurchaseRequisition.objects.filter(tenant=tenant_a).order_by("-id").first()
        # Raised in the SIGNED-IN user's name, as a DRAFT, with a DERIVED total.
        assert pr.requester_id == admin_user.pk
        assert pr.status == "draft"
        assert pr.lines.count() == 1
        assert pr.lines.first().item_description == "Toner cartridge"
        assert str(pr.estimated_total) == "99.80"
        # Hands off to scm's detail page for submit/approve.
        assert reverse("scm:requisition_detail", kwargs={"pk": pr.pk}) in resp["Location"]
        # And the mutation is on the audit trail the activity feed reads.
        assert AuditLog.objects.filter(
            content_type__app_label="scm",
            content_type__model="purchaserequisition",
            object_id=pr.pk, action="create").exists()

    def test_invalid_post_rerenders_with_errors(self, client_a, tenant_a):
        before = _pr_count(tenant_a)
        resp = self._post(client_a, title="")
        assert resp.status_code == 200
        assert _pr_count(tenant_a) == before
        assert b"This field is required" in resp.content or b"required" in resp.content.lower()


# ------------------------------------------------------------------ alert lifecycle via views


class TestAlertLifecycleViews:
    def test_full_crud_cycle(self, client_a, tenant_a, admin_user):
        resp = client_a.post(reverse("procurement:alert_create"), {
            "kind": "task", "severity": "warning", "title": "View-cycle alert",
            "message": "m", "link_url": "", "due_at": "", "assigned_to": ""})
        assert resp.status_code == 302
        alert = ProcurementAlert.objects.get(tenant=tenant_a, title="View-cycle alert")
        assert alert.created_by_id == admin_user.pk  # authorship stamped by the view

        resp = client_a.post(reverse("procurement:alert_edit", kwargs={"pk": alert.pk}), {
            "kind": "task", "severity": "critical", "title": "View-cycle alert v2",
            "message": "m2", "link_url": "", "due_at": "", "assigned_to": ""})
        assert resp.status_code == 302
        alert.refresh_from_db()
        assert alert.severity == "critical"

        client_a.post(reverse("procurement:alert_acknowledge", kwargs={"pk": alert.pk}))
        alert.refresh_from_db()
        assert alert.status == "acknowledged"

        client_a.post(reverse("procurement:alert_resolve", kwargs={"pk": alert.pk}),
                      {"resolution_note": "done"})
        alert.refresh_from_db()
        assert alert.status == "resolved" and alert.resolution_note == "done"

    def test_double_resolve_never_restamps(self, client_a, alert_resolved, admin_user):
        """CR-2 regression at the view layer: the second POST must be an info, not a rewrite."""
        who, when = alert_resolved.resolved_by_id, alert_resolved.resolved_at
        resp = client_a.post(reverse("procurement:alert_resolve",
                                     kwargs={"pk": alert_resolved.pk}),
                             {"resolution_note": "hijack"})
        assert resp.status_code == 302
        alert_resolved.refresh_from_db()
        assert alert_resolved.resolved_by_id == who
        assert alert_resolved.resolved_at == when
        assert alert_resolved.resolution_note != "hijack"

    def test_delete_is_post_only_and_removes(self, client_a, alert_open):
        url = reverse("procurement:alert_delete", kwargs={"pk": alert_open.pk})
        assert client_a.get(url).status_code == 405  # GET never mutates
        assert client_a.post(url).status_code == 302
        assert not ProcurementAlert.objects.filter(pk=alert_open.pk).exists()

    def test_list_floats_open_rows_above_old_resolved_ones(self, client_a, tenant_a):
        old_resolved = ProcurementAlert.objects.create(
            tenant=tenant_a, kind="task", severity="info", status="resolved",
            title="AAA resolved long ago", resolved_at=timezone.now())
        fresh_open = ProcurementAlert.objects.create(
            tenant=tenant_a, kind="task", severity="critical", status="open",
            title="ZZZ fresh open")
        html = client_a.get(reverse("procurement:alert_list")).content.decode()
        assert html.index("ZZZ fresh open") < html.index("AAA resolved long ago")


# ------------------------------------------------------------------ activity feed


class TestActivityFeed:
    def _feed_row(self, tenant, user, target="PR-00001 · paper"):
        from django.contrib.contenttypes.models import ContentType
        return AuditLog.objects.create(
            tenant=tenant, user=user,
            content_type=ContentType.objects.get(app_label="scm",
                                                 model="purchaserequisition"),
            object_id=1, target=target, action="create")

    def test_scope_mine_vs_all(self, client_a, tenant_a, admin_user, member_user):
        mine = self._feed_row(tenant_a, admin_user, "mine-row")
        theirs = self._feed_row(tenant_a, member_user, "theirs-row")
        mine_page = client_a.get(reverse("procurement:activity_list"), {"scope": "mine"})
        assert b"mine-row" in mine_page.content
        assert b"theirs-row" not in mine_page.content
        all_page = client_a.get(reverse("procurement:activity_list"), {"scope": "all"})
        assert b"mine-row" in all_page.content and b"theirs-row" in all_page.content

    def test_junk_action_token_narrows_nothing(self, client_a, tenant_a, admin_user):
        """A closed vocabulary: junk narrows NOTHING instead of rendering a lying empty page."""
        row = self._feed_row(tenant_a, admin_user, "visible-row")
        resp = client_a.get(reverse("procurement:activity_list"),
                            {"scope": "all", "action": "browsed"})
        assert b"visible-row" in resp.content

    def test_action_filter_applies_when_valid(self, client_a, tenant_a, admin_user):
        created = self._feed_row(tenant_a, admin_user, "created-row")
        deleted = AuditLog.objects.create(
            tenant=tenant_a, user=admin_user, content_type=created.content_type,
            object_id=1, target="deleted-row", action="delete")
        resp = client_a.get(reverse("procurement:activity_list"),
                            {"scope": "all", "action": "delete"})
        assert b"deleted-row" in resp.content and b"created-row" not in resp.content

    def test_feed_is_windowed_to_thirty_days_by_default(self, client_a, tenant_a,
                                                        admin_user):
        from apps.procurement.views._helpers import procurement_activity_qs
        row = self._feed_row(tenant_a, admin_user, "old-row")
        old = timezone.now() - datetime.timedelta(days=60)
        type(row).objects.filter(pk=row.pk).update(at=old)
        resp = client_a.get(reverse("procurement:activity_list"), {"scope": "all"})
        assert b"old-row" not in resp.content
        assert b"default" in resp.content.lower()  # the page SAYS it defaulted

    def test_detail_shows_field_changes(self, client_a, tenant_a, admin_user):
        from django.contrib.contenttypes.models import ContentType
        ct = ContentType.objects.get(app_label="scm", model="purchaserequisition")
        row = AuditLog.objects.create(
            tenant=tenant_a, user=admin_user, content_type=ct, object_id=1,
            target="PR-00001", action="update", changes={"status": "approved"})
        resp = client_a.get(reverse("procurement:activity_detail", kwargs={"pk": row.pk}))
        assert resp.status_code == 200
        assert b"status" in resp.content and b"approved" in resp.content


# ------------------------------------------------------------------ reports


class TestReports:
    def test_personal_usage_counts_by_status(self, client_a, tenant_a, admin_user):
        for i in range(3):
            PurchaseRequisition.objects.create(tenant=tenant_a, requester=admin_user,
                                               title=f"r{i}")
        resp = client_a.get(reverse("procurement:report_index"))
        assert resp.status_code == 200
        assert b"My Requisitions by Status" in resp.content

    def test_csv_export_is_my_rows_only_and_formula_safe(self, client_a, tenant_a,
                                                         tenant_b, admin_user):
        from apps.scm.models import PurchaseRequisition
        dangerous = PurchaseRequisition.objects.create(
            tenant=tenant_a, requester=admin_user, title="=HYPERLINK(\"http://evil\")")
        other_member = PurchaseRequisition.objects.create(
            tenant=tenant_a, requester=None, title="unassigned row")
        foreign = PurchaseRequisition.objects.create(
            tenant=tenant_b, requester=admin_user, title="globex row")
        resp = client_a.get(reverse("procurement:report_export"))
        body = resp.content.decode()
        # csv.writer quotes the doubled inner quotes; the CELL must start with an
        # apostrophe so Excel never evaluates it, i.e. no field may OPEN with '='.
        assert "'=HYPERLINK" in body
        assert ',"=' not in body and "\n=" not in body
        assert "globex row" not in body          # another tenant's row absent
        assert "unassigned row" not in body      # export is MY requisitions only
