"""Inventory 5.2 — security.

Cross-tenant IDOR on every route shape (GET pages, edit POSTs, delete POSTs), list
isolation, POST-only destructive verbs, anonymous access, CSRF enforcement, escaping of
logged interaction text, and the junk-input degradation contract.
"""
import pytest
from django.test import Client
from django.urls import reverse

from apps.inventory.models import VendorCommunication

pytestmark = pytest.mark.django_db


def test_cross_tenant_detail_and_edit_404(client_a, communication_b):
    for name in ["vendorcommunication_detail", "vendorcommunication_edit"]:
        assert client_a.get(reverse(f"inventory:{name}", args=[communication_b.pk])).status_code == 404


def test_cross_tenant_edit_post_404_and_row_unchanged(client_a, communication_b):
    response = client_a.post(
        reverse("inventory:vendorcommunication_edit", args=[communication_b.pk]),
        data={"subject": "hijacked"})
    assert response.status_code == 404
    communication_b.refresh_from_db()
    assert communication_b.subject != "hijacked"


def test_cross_tenant_delete_post_404_and_row_survives(client_a, communication_b):
    """The destructive verb is where an IDOR would do damage: a foreign pk must 404 on
    POST and leave the other workspace's interaction history untouched."""
    response = client_a.post(reverse("inventory:vendorcommunication_delete",
                                     args=[communication_b.pk]))
    assert response.status_code == 404
    communication_b.refresh_from_db()  # raises if the row was deleted — the real assertion


def test_foreign_rows_never_leak_into_lists(client_a, communication_b):
    content = client_a.get(reverse("inventory:vendorcommunication_list")).content
    assert communication_b.subject.encode() not in content
    assert communication_b.number.encode() not in content


def test_delete_is_post_only(client_a, communication_a):
    assert client_a.get(reverse("inventory:vendorcommunication_delete",
                                args=[communication_a.pk])).status_code == 405


def test_crafted_post_cannot_create_cross_tenant_row(client_a, tenant_a, tenant_b,
                                                     vendor_party_b, vendor_party_a):
    """`tenant` is excluded from the form and crud_create stamps request.tenant — a crafted
    foreign tenant/pair must end up either rejected or re-stamped to the session's tenant,
    never saved under tenant_b."""
    client_a.post(reverse("inventory:vendorcommunication_create"), data={
        "party": vendor_party_b.pk, "channel": "note", "direction": "",
        "subject": "crafted", "body": "", "occurred_at": "2026-08-20 10:00",
        "follow_up_on": "", "tenant": tenant_b.pk})
    assert not VendorCommunication.objects.filter(tenant_id=tenant_b.pk).exists()
    assert not VendorCommunication.objects.filter(subject="crafted", tenant_id=tenant_b.pk).exists()


def test_anonymous_redirected_on_every_page(client, communication_a):
    for name in ["vendorcommunication_list", "vendorcommunication_create"]:
        response = client.get(reverse(f"inventory:{name}"))
        assert response.status_code == 302
        assert "/login" in response.url or response.url.endswith("login")
    for name in ["vendorcommunication_detail", "vendorcommunication_edit"]:
        response = client.get(reverse(f"inventory:{name}", args=[communication_a.pk]))
        assert response.status_code == 302
        assert "/login" in response.url or response.url.endswith("login")


@pytest.fixture
def csrf_client(admin_user):
    strict = Client(enforce_csrf_checks=True)
    strict.force_login(admin_user)
    return strict


def test_csrf_refused_on_create_and_delete(csrf_client, vendor_party_a, communication_a):
    create = csrf_client.post(reverse("inventory:vendorcommunication_create"), data={
        "party": vendor_party_a.pk, "channel": "note", "direction": "",
        "subject": "X", "body": "", "occurred_at": "2026-08-20 10:00", "follow_up_on": ""})
    delete = csrf_client.post(reverse("inventory:vendorcommunication_delete",
                                      args=[communication_a.pk]))
    assert create.status_code == 403
    assert delete.status_code == 403
    communication_a.refresh_from_db()  # nothing was deleted despite the valid session


def test_logged_text_is_escaped_not_executed(client_a, vendor_party_a):
    """A logged interaction's subject renders escaped on detail — autoescape is the only
    sanitizer a log of free-text vendor conversations may rely on."""
    probe = "<script>alert(1)</script>"
    response = client_a.post(reverse("inventory:vendorcommunication_create"), data={
        "party": vendor_party_a.pk, "channel": "note", "direction": "",
        "subject": probe, "body": "", "occurred_at": "2026-08-20 10:00", "follow_up_on": ""})
    assert response.status_code == 302
    row = VendorCommunication.objects.get(subject=probe)
    try:
        detail = client_a.get(reverse("inventory:vendorcommunication_detail", args=[row.pk]))
        assert "&lt;script&gt;" in detail.content.decode()
        assert probe not in detail.content.decode()
    finally:
        row.delete()


def test_junk_pk_filters_degrade_not_500(client_a, vendor_party_a):
    """L11: a GET value that is not a pk skips the filter instead of raising out of .filter()."""
    base = reverse("inventory:vendorcommunication_list")
    for query in [f"?party={vendor_party_a.pk}", "?party=abc", "?party=999999999999999999999",
                  "?party=%C2%B2"]:
        assert client_a.get(base + query).status_code == 200


def test_siblings_panel_is_tenant_scoped(client_a, tenant_b, communication_a,
                                         vendor_party_a, communication_b):
    """The detail page's per-vendor history shows same-workspace rows only."""
    sibling = VendorCommunication.objects.create(
        tenant=communication_a.tenant, party=vendor_party_a, channel="email",
        subject="Sibling interaction")
    content = client_a.get(reverse("inventory:vendorcommunication_detail",
                                   args=[communication_a.pk])).content
    assert sibling.number.encode() in content
    # Numbers are per-tenant (both workspaces' first rows read VC-00001), so isolation is
    # asserted on the foreign row's SUBJECT — the same rule the list-isolation test uses.
    assert communication_b.subject.encode() not in content
