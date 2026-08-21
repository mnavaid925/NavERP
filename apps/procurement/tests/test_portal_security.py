"""Procurement 6.1 - security posture.

Tenant isolation is the headline: every read, write and lifecycle verb must 404 across the
tenant line with the foreign row untouched, the feed must never leak another domain's audit
rows, and nothing may mutate on GET.
"""
import pytest
from django.urls import reverse

from apps.core.models import AuditLog
from apps.procurement.models import ProcurementAlert, WidgetPreference

pytestmark = pytest.mark.django_db


# ------------------------------------------------------------------ cross-tenant IDOR


class TestCrossTenantIsolation:
    def test_detail_404s(self, client_a, alert_b):
        resp = client_a.get(reverse("procurement:alert_detail",
                                    kwargs={"pk": alert_b.pk}))
        assert resp.status_code == 404

    def test_edit_get_and_post_404(self, client_a, alert_b):
        url = reverse("procurement:alert_edit", kwargs={"pk": alert_b.pk})
        assert client_a.get(url).status_code == 404
        resp = client_a.post(url, {"kind": "task", "severity": "info",
                                   "title": "hijacked", "message": "", "link_url": "",
                                   "due_at": "", "assigned_to": ""})
        assert resp.status_code == 404
        alert_b.refresh_from_db()
        assert alert_b.title != "hijacked"

    def test_delete_404_and_row_survives(self, client_a, alert_b):
        assert client_a.post(reverse("procurement:alert_delete",
                                     kwargs={"pk": alert_b.pk})).status_code == 404
        assert ProcurementAlert.objects.filter(pk=alert_b.pk).exists()

    def test_lifecycle_actions_404(self, client_a, alert_b):
        for action in ("alert_acknowledge", "alert_resolve"):
            url = reverse(f"procurement:{action}", kwargs={"pk": alert_b.pk})
            assert client_a.post(url, {}).status_code == 404
        alert_b.refresh_from_db()
        assert alert_b.status == "open"

    def test_list_never_shows_foreign_rows(self, client_a, alert_open, alert_b):
        html = client_a.get(reverse("procurement:alert_list")).content.decode()
        assert alert_open.title in html
        assert alert_b.title not in html


# ------------------------------------------------------------------ authn / verbs


class TestAuthAndVerbs:
    @pytest.mark.parametrize("name", ["dashboard", "alert_list", "alert_create",
                                      "quickreq_create", "activity_list",
                                      "report_index", "report_export"])
    def test_anonymous_is_redirected_to_login(self, db, name):
        from django.test import Client
        resp = Client().get(reverse(f"procurement:{name}"))
        assert resp.status_code == 302
        assert "/login/" in resp["Location"]

    @pytest.mark.parametrize("name", ["alert_acknowledge", "alert_resolve",
                                      "alert_delete"])
    def test_state_changes_are_post_only(self, client_a, alert_open, name):
        url = reverse(f"procurement:{name}", kwargs={"pk": alert_open.pk})
        assert client_a.get(url).status_code == 405
        alert_open.refresh_from_db()
        assert alert_open.status == "open"

    def test_widget_toggle_never_mutates_on_get(self, client_a, tenant_a, admin_user):
        """A GET on the dashboard must never change anyone's layout."""
        client_a.get(reverse("procurement:dashboard"))
        assert WidgetPreference.objects.filter(tenant=tenant_a,
                                               user=admin_user).count() == 0


# ------------------------------------------------------------------ feed domain filter


class TestFeedDomainFilter:
    def _foreign_domain_row(self, tenant_a, admin_user):
        from django.contrib.contenttypes.models import ContentType
        return AuditLog.objects.create(
            tenant=tenant_a, user=admin_user,
            content_type=ContentType.objects.get(app_label="crm", model="lead"),
            object_id=1, target="Lead · somebody else's domain", action="create")

    def test_feed_hides_non_procurement_audit_rows(self, client_a, tenant_a, admin_user):
        row = self._foreign_domain_row(tenant_a, admin_user)
        resp = client_a.get(reverse("procurement:activity_list"), {"scope": "all"})
        assert row.target.encode() not in resp.content

    def test_activity_detail_404s_on_foreign_domain_pk(self, client_a, tenant_a,
                                                       admin_user):
        """Guessed pks from other modules' URLs must not render here even in-tenant."""
        row = self._foreign_domain_row(tenant_a, admin_user)
        resp = client_a.get(reverse("procurement:activity_detail",
                                    kwargs={"pk": row.pk}))
        assert resp.status_code == 404


# ------------------------------------------------------------------ input hardening


class TestInputHardening:
    def test_alert_link_cannot_point_off_site_via_form(self, client_a, tenant_a):
        resp = client_a.post(reverse("procurement:alert_create"), {
            "kind": "task", "severity": "info", "title": "phishy",
            "message": "", "link_url": "//evil.com", "due_at": "", "assigned_to": ""})
        assert resp.status_code == 200  # re-render with errors, nothing created
        assert not ProcurementAlert.objects.filter(tenant=tenant_a,
                                                   title="phishy").exists()
        assert b"internal path" in resp.content or b"single slash" in resp.content

    def test_csv_export_neutralizes_formula_cells(self, client_a, tenant_a, admin_user):
        from apps.scm.models import PurchaseRequisition
        PurchaseRequisition.objects.create(tenant=tenant_a, requester=admin_user,
                                           title="=cmd|' /C calc'!A0")
        resp = client_a.get(reverse("procurement:report_export"))
        body = resp.content.decode()
        assert "'=cmd" in body and "\n=cmd" not in body

    def test_quickreq_cannot_forge_requester_or_total(self, client_a, tenant_a,
                                                      member_user, admin_user):
        """requester is hardwired to the session user; estimated_total is derived."""
        from apps.scm.models import PurchaseRequisition
        before = PurchaseRequisition.objects.filter(tenant=tenant_a).count()
        resp = client_a.post(reverse("procurement:quickreq_create"), {
            "title": "Forged?", "item_description": "x", "quantity": "2",
            "estimated_unit_price": "10", "uom_hint": "", "sku_hint": "",
            "currency": "", "gl_account": "", "org_unit": "",
            "required_by": "", "justification": ""})
        assert resp.status_code == 302
        pr = PurchaseRequisition.objects.filter(tenant=tenant_a).order_by("-id").first()
        assert pr.requester_id == admin_user.pk          # the SESSION user, always
        assert str(pr.estimated_total) == "20.00"        # qty x price, server-side
        assert PurchaseRequisition.objects.filter(tenant=tenant_a).count() == before + 1

    def test_member_can_use_the_portal_but_only_their_own_prefs(
            self, member_client, tenant_a, member_user, admin_user):
        resp = member_client.post(reverse("procurement:dashboard"),
                                  {"widgets": ["spend"]})
        assert resp.status_code == 302
        hidden = set(WidgetPreference.objects.filter(tenant=tenant_a)
                     .values_list("user_id", flat=True))
        assert hidden == {member_user.pk}  # never anybody else's rows
