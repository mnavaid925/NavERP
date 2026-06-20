"""Security tests: CSRF enforcement, IDOR, auth on every endpoint."""
import pytest
from django.test import Client
from django.urls import reverse

pytestmark = pytest.mark.django_db


class TestCSRF:
    """Verify that POST-only delete endpoints require CSRF (enforced middleware)."""

    def test_party_delete_enforces_csrf(self, party_a, admin_user):
        """A client without CSRF token on POST must receive 403."""
        # Django test client by default enforces CSRF via enforce_csrf_checks=True
        c = Client(enforce_csrf_checks=True)
        c.force_login(admin_user)
        resp = c.post(reverse("core:party_delete", args=[party_a.pk]))
        assert resp.status_code == 403

    def test_orgunit_delete_enforces_csrf(self, tenant_a, admin_user):
        from apps.core.models import OrgUnit
        ou = OrgUnit.objects.create(tenant=tenant_a, name="Test")
        c = Client(enforce_csrf_checks=True)
        c.force_login(admin_user)
        resp = c.post(reverse("core:orgunit_delete", args=[ou.pk]))
        assert resp.status_code == 403


class TestAnonymousAccess:
    """All tenant-scoped views must redirect anonymous users to login."""

    URLS = [
        ("core:party_list", []),
        ("core:orgunit_list", []),
        ("core:auditlog_list", []),
        ("core:activity_list", []),
        ("core:employment_list", []),
        ("core:address_list", []),
        ("core:contactmethod_list", []),
    ]

    @pytest.mark.parametrize("url_name,args", [
        ("core:party_list", []),
        ("core:orgunit_list", []),
        ("core:auditlog_list", []),
        ("core:activity_list", []),
        ("core:employment_list", []),
        ("core:address_list", []),
        ("core:contactmethod_list", []),
    ])
    def test_anon_redirected(self, client, url_name, args):
        resp = client.get(reverse(url_name, args=args))
        assert resp.status_code == 302
        assert "login" in resp["Location"]


class TestMemberCanReadButAdminRequired:
    """Non-admin members can read most core views but not the AuditLog."""

    def test_member_can_access_party_list(self, member_client):
        resp = member_client.get(reverse("core:party_list"))
        assert resp.status_code == 200

    def test_member_blocked_from_auditlog(self, member_client):
        resp = member_client.get(reverse("core:auditlog_list"))
        assert resp.status_code == 403

    def test_member_can_create_party(self, member_client, tenant_a):
        from apps.core.models import Party
        resp = member_client.post(reverse("core:party_create"), {
            "kind": "person",
            "name": "Member Created",
            "tax_id": "",
        })
        assert resp.status_code == 302
        assert Party.objects.filter(tenant=tenant_a, name="Member Created").exists()
