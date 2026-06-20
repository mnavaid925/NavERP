"""Tests for core CRUD views: auth redirect, CRUD flow, multi-tenant IDOR."""
import pytest
from django.urls import reverse

pytestmark = pytest.mark.django_db


# ---------------------------------------------------------------- Auth redirect
class TestAuthRedirect:
    def test_party_list_anon_redirects_to_login(self, client):
        url = reverse("core:party_list")
        resp = client.get(url)
        assert resp.status_code == 302
        assert "/auth/login/" in resp["Location"] or "login" in resp["Location"]

    def test_orgunit_list_anon_redirects(self, client):
        url = reverse("core:orgunit_list")
        resp = client.get(url)
        assert resp.status_code == 302


# ---------------------------------------------------------------- Party CRUD
class TestPartyCRUD:
    def test_list_200(self, client_a):
        resp = client_a.get(reverse("core:party_list"))
        assert resp.status_code == 200
        assert "object_list" in resp.context

    def test_create_post_302_and_persists(self, client_a, tenant_a):
        from apps.core.models import Party
        resp = client_a.post(reverse("core:party_create"), {
            "kind": "organization",
            "name": "Test Corp",
            "tax_id": "12-3456789",
        })
        assert resp.status_code == 302
        assert Party.objects.filter(tenant=tenant_a, name="Test Corp").exists()

    def test_create_sets_tenant(self, client_a, tenant_a):
        from apps.core.models import Party
        client_a.post(reverse("core:party_create"), {
            "kind": "person",
            "name": "Jane Doe",
            "tax_id": "",
        })
        p = Party.objects.get(tenant=tenant_a, name="Jane Doe")
        assert p.tenant == tenant_a

    def test_detail_200(self, client_a, party_a):
        resp = client_a.get(reverse("core:party_detail", args=[party_a.pk]))
        assert resp.status_code == 200
        assert resp.context["obj"] == party_a

    def test_edit_get_200(self, client_a, party_a):
        resp = client_a.get(reverse("core:party_edit", args=[party_a.pk]))
        assert resp.status_code == 200
        assert resp.context["is_edit"] is True

    def test_edit_post_updates(self, client_a, party_a):
        from apps.core.models import Party
        resp = client_a.post(reverse("core:party_edit", args=[party_a.pk]), {
            "kind": "organization",
            "name": "Acme Updated",
            "tax_id": "",
        })
        assert resp.status_code == 302
        party_a.refresh_from_db()
        assert party_a.name == "Acme Updated"

    def test_delete_post_removes(self, client_a, party_a, tenant_a):
        from apps.core.models import Party
        pk = party_a.pk
        resp = client_a.post(reverse("core:party_delete", args=[pk]))
        assert resp.status_code == 302
        assert not Party.objects.filter(pk=pk).exists()

    def test_list_search(self, client_a, tenant_a):
        from apps.core.models import Party
        Party.objects.create(tenant=tenant_a, name="Alpha Corp")
        Party.objects.create(tenant=tenant_a, name="Beta Inc")
        resp = client_a.get(reverse("core:party_list") + "?q=Alpha")
        assert resp.status_code == 200
        names = [p.name for p in resp.context["object_list"]]
        assert "Alpha Corp" in names
        assert "Beta Inc" not in names

    def test_list_has_page_obj(self, client_a):
        resp = client_a.get(reverse("core:party_list"))
        assert "page_obj" in resp.context


# ---------------------------------------------------------------- Multi-tenant IDOR
class TestMultiTenantIDOR:
    """Tenant A admin attempting to access Tenant B objects → 404."""

    def test_party_detail_cross_tenant_404(self, client_a, party_b):
        resp = client_a.get(reverse("core:party_detail", args=[party_b.pk]))
        assert resp.status_code == 404

    def test_party_edit_cross_tenant_404(self, client_a, party_b):
        resp = client_a.get(reverse("core:party_edit", args=[party_b.pk]))
        assert resp.status_code == 404

    def test_party_edit_post_cross_tenant_404(self, client_a, party_b):
        resp = client_a.post(reverse("core:party_edit", args=[party_b.pk]), {
            "kind": "organization",
            "name": "Hacked",
            "tax_id": "",
        })
        assert resp.status_code == 404

    def test_party_delete_cross_tenant_404(self, client_a, party_b):
        from apps.core.models import Party
        resp = client_a.post(reverse("core:party_delete", args=[party_b.pk]))
        assert resp.status_code == 404
        # Object must still exist
        assert Party.objects.filter(pk=party_b.pk).exists()

    def test_party_list_only_shows_own_tenant(self, client_a, party_a, party_b):
        resp = client_a.get(reverse("core:party_list"))
        pks = [p.pk for p in resp.context["object_list"]]
        assert party_a.pk in pks
        assert party_b.pk not in pks

    def test_orgunit_cross_tenant_detail_404(self, client_a, tenant_b):
        from apps.core.models import OrgUnit
        ou_b = OrgUnit.objects.create(tenant=tenant_b, name="B Dept")
        resp = client_a.get(reverse("core:orgunit_detail", args=[ou_b.pk]))
        assert resp.status_code == 404


# ---------------------------------------------------------------- OrgUnit CRUD
class TestOrgUnitCRUD:
    def test_list_200(self, client_a):
        resp = client_a.get(reverse("core:orgunit_list"))
        assert resp.status_code == 200

    def test_create_post_sets_tenant(self, client_a, tenant_a):
        from apps.core.models import OrgUnit
        client_a.post(reverse("core:orgunit_create"), {
            "kind": "department",
            "name": "R&D",
        })
        assert OrgUnit.objects.filter(tenant=tenant_a, name="R&D").exists()

    def test_delete_post(self, client_a, tenant_a):
        from apps.core.models import OrgUnit
        ou = OrgUnit.objects.create(tenant=tenant_a, name="Temp Dept")
        resp = client_a.post(reverse("core:orgunit_delete", args=[ou.pk]))
        assert resp.status_code == 302
        assert not OrgUnit.objects.filter(pk=ou.pk).exists()


# ---------------------------------------------------------------- AuditLog view
class TestAuditLogView:
    def test_auditlog_list_admin_only_200(self, client_a, tenant_a, admin_user, party_a):
        from apps.core.utils import write_audit_log
        write_audit_log(admin_user, party_a, "create")
        resp = client_a.get(reverse("core:auditlog_list"))
        assert resp.status_code == 200

    def test_auditlog_list_member_403(self, member_client):
        resp = member_client.get(reverse("core:auditlog_list"))
        assert resp.status_code == 403

    def test_auditlog_detail_200(self, client_a, tenant_a, admin_user, party_a):
        from apps.core.utils import write_audit_log
        log = write_audit_log(admin_user, party_a, "create")
        resp = client_a.get(reverse("core:auditlog_detail", args=[log.pk]))
        assert resp.status_code == 200

    def test_auditlog_detail_cross_tenant_404(self, client_b, tenant_a, admin_user, party_a):
        from apps.core.utils import write_audit_log
        log = write_audit_log(admin_user, party_a, "create")
        # client_b is tenant B — AuditLog belongs to tenant A
        resp = client_b.get(reverse("core:auditlog_detail", args=[log.pk]))
        assert resp.status_code == 404
