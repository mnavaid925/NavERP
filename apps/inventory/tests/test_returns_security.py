"""Inventory 5.10 Returns Management — multi-tenancy IDOR & security tests."""
import pytest
from django.urls import reverse

pytestmark = pytest.mark.django_db


def test_returninspection_detail_idor_isolated(client_a, inspection_b):
    """Tenant A admin cannot view Tenant B's return inspection (404)."""
    url = reverse("inventory:returninspection_detail", kwargs={"pk": inspection_b.pk})
    resp = client_a.get(url)
    assert resp.status_code == 404


def test_returninspection_edit_idor_isolated(client_a, inspection_b):
    """Tenant A admin cannot edit Tenant B's return inspection (404)."""
    url = reverse("inventory:returninspection_edit", kwargs={"pk": inspection_b.pk})
    resp = client_a.get(url)
    assert resp.status_code == 404


def test_returninspection_delete_idor_isolated(client_a, inspection_b):
    """Tenant A admin cannot delete Tenant B's return inspection (404)."""
    url = reverse("inventory:returninspection_delete", kwargs={"pk": inspection_b.pk})
    resp = client_a.post(url)
    assert resp.status_code == 404


def test_dispositionrule_detail_idor_isolated(client_a, disposition_rule_b):
    """Tenant A admin cannot view Tenant B's disposition routing rule (404)."""
    url = reverse("inventory:dispositionrule_detail", kwargs={"pk": disposition_rule_b.pk})
    resp = client_a.get(url)
    assert resp.status_code == 404


def test_dispositionrule_edit_idor_isolated(client_a, disposition_rule_b):
    """Tenant A admin cannot edit Tenant B's disposition routing rule (404)."""
    url = reverse("inventory:dispositionrule_edit", kwargs={"pk": disposition_rule_b.pk})
    resp = client_a.get(url)
    assert resp.status_code == 404


def test_dispositionrule_write_requires_admin(member_client_a, disposition_rule_a):
    """Regular member cannot access disposition rule write views (403)."""
    create_url = reverse("inventory:dispositionrule_create")
    assert member_client_a.get(create_url).status_code == 403

    edit_url = reverse("inventory:dispositionrule_edit", kwargs={"pk": disposition_rule_a.pk})
    assert member_client_a.get(edit_url).status_code == 403

    delete_url = reverse("inventory:dispositionrule_delete", kwargs={"pk": disposition_rule_a.pk})
    assert member_client_a.post(delete_url).status_code == 403
