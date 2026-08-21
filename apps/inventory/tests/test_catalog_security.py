"""Inventory 5.1 — security.

Cross-tenant IDOR on every route shape (GET pages, edit POSTs, delete POSTs), anonymous
access, CSRF enforcement, and the junk-input degradation contract.
"""
import pytest
from django.test import Client
from django.urls import reverse

pytestmark = pytest.mark.django_db


def test_cross_tenant_detail_and_edit_404(client_a, attribute_b, price_b, product_file_b):
    for name, pk in [
        ("inventory:itemattribute_detail", attribute_b.pk),
        ("inventory:itemattribute_edit", attribute_b.pk),
        ("inventory:itemprice_detail", price_b.pk),
        ("inventory:itemprice_edit", price_b.pk),
        ("inventory:productfile_detail", product_file_b.pk),
        ("inventory:productfile_edit", product_file_b.pk),
    ]:
        assert client_a.get(reverse(name, args=[pk])).status_code == 404


def test_cross_tenant_delete_post_404_and_row_survives(client_a, attribute_b, price_b,
                                                       product_file_b):
    """The destructive verbs are where an IDOR would do damage: a foreign pk must 404 on POST
    and leave the other workspace's row untouched."""
    for name, obj in [
        ("inventory:itemattribute_delete", attribute_b),
        ("inventory:itemprice_delete", price_b),
        ("inventory:productfile_delete", product_file_b),
    ]:
        response = client_a.post(reverse(name, args=[obj.pk]))
        assert response.status_code == 404
        obj.refresh_from_db()  # raises if the row was deleted — the real assertion


def test_foreign_rows_never_leak_into_lists(client_a, attribute_b):
    content = client_a.get(reverse("inventory:itemattribute_list")).content
    # the foreign row's VALUE never renders (its SKU "CAT-1" legitimately matches tenant_a's
    # own item — same sku, different workspace — so assert on the value, not the code)
    assert b"Safety Yellow" not in content


def test_anonymous_redirected_on_every_page(client):
    for name in ["inventory:overview", "inventory:itemattribute_list",
                 "inventory:itemprice_list", "inventory:productfile_list"]:
        response = client.get(reverse(name))
        assert response.status_code == 302
        assert "/login" in response.url or response.url.endswith("login")


@pytest.fixture
def csrf_client(admin_user):
    """A logged-in client with CSRF enforcement ON — a stolen-session POST without a token
    must still be refused on both the create and the destructive path."""
    strict = Client(enforce_csrf_checks=True)
    strict.force_login(admin_user)
    return strict


def test_csrf_refused_on_create_and_delete(csrf_client, item_a, attribute_a):
    create = csrf_client.post(reverse("inventory:itemattribute_create"), data={
        "item": item_a.pk, "name": "X", "value": "Y", "unit": "", "sequence": "0"})
    delete = csrf_client.post(reverse("inventory:itemattribute_delete", args=[attribute_a.pk]))
    assert create.status_code == 403
    assert delete.status_code == 403
    attribute_a.refresh_from_db()  # nothing was deleted despite the valid session


@pytest.mark.parametrize("query", ["?item=abc", "?item=999999999999999999999", "?item=%C2%B2"])
def test_junk_pk_filters_degrade_not_500(client_a, query):
    """L11: a GET value that is not a pk skips the filter instead of raising out of .filter()."""
    assert client_a.get(reverse("inventory:itemattribute_list") + query).status_code == 200
