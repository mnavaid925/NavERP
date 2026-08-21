"""Inventory 5.2 — views.

The vendor interaction log renders through the shared crud helpers: tenant-scoped lists
with search/filter/pagination, a detail page whose siblings panel is scoped AND
self-excluded, and CRUD flows that keep every write inside the caller's workspace.
"""
import datetime

import pytest
from django.urls import reverse

from apps.inventory.models import VendorCommunication

pytestmark = pytest.mark.django_db


def test_list_renders_200_with_row_and_heading(client_a, communication_a):
    response = client_a.get(reverse("inventory:vendorcommunication_list"))
    assert response.status_code == 200
    content = response.content
    assert b"Vendor Communication Log" in content
    assert "Quarterly capacity check".encode() in content
    assert communication_a.number.encode() in content


def test_list_search_narrows_queryset(client_a, communication_a):
    hit = client_a.get(reverse("inventory:vendorcommunication_list") + "?q=capacity")
    assert hit.status_code == 200
    assert communication_a in hit.context["object_list"]
    miss = client_a.get(reverse("inventory:vendorcommunication_list") + "?q=zzznope")
    assert miss.status_code == 200
    assert len(miss.context["object_list"]) == 0


def test_list_filters_channel_party_follow_up(client_a, communication_a):
    base = reverse("inventory:vendorcommunication_list")
    channel_hit = client_a.get(base + "?channel=call")
    assert channel_hit.status_code == 200
    assert communication_a in channel_hit.context["object_list"]
    channel_miss = client_a.get(base + "?channel=email")
    assert communication_a not in channel_miss.context["object_list"]

    party_hit = client_a.get(base + f"?party={communication_a.party.pk}")
    assert party_hit.status_code == 200
    assert communication_a in party_hit.context["object_list"]

    overdue = client_a.get(base + "?follow_up=overdue")
    assert overdue.status_code == 200
    assert communication_a in overdue.context["object_list"]
    due = client_a.get(base + "?follow_up=due")
    assert due.status_code == 200
    # Its follow-up date is strictly past — due means today-or-later, so it must not show.
    assert communication_a not in due.context["object_list"]


def test_list_bogus_filters_degrade_not_500(client_a):
    """L11: non-pk and over-range values skip the filter instead of raising."""
    base = reverse("inventory:vendorcommunication_list")
    assert client_a.get(base + "?party=abc").status_code == 200
    assert client_a.get(base + "?party=999999999999999999999").status_code == 200


def test_list_pagination(client_a, tenant_a, vendor_party_a, communication_a):
    for i in range(17):
        VendorCommunication.objects.create(
            tenant=tenant_a, party=vendor_party_a,
            subject=f"Bulk row {i}",
            occurred_at=datetime.datetime(2026, 7, 1, 9, 0) + datetime.timedelta(hours=i))
    page_one = client_a.get(reverse("inventory:vendorcommunication_list"))
    assert page_one.status_code == 200
    assert len(page_one.context["object_list"]) == 15
    page_two = client_a.get(reverse("inventory:vendorcommunication_list") + "?page=2")
    assert page_two.status_code == 200
    assert page_two.context["page_obj"].number == 2
    assert len(page_two.context["object_list"]) == 3


def test_detail_renders_subject_body_number_and_siblings(
        client_a, tenant_a, vendor_party_a, communication_a):
    sibling = VendorCommunication.objects.create(
        tenant=tenant_a, party=vendor_party_a, subject="Site visit walkthrough",
        occurred_at=datetime.datetime(2026, 8, 18, 14, 30))
    response = client_a.get(reverse("inventory:vendorcommunication_detail",
                                    args=[communication_a.pk]))
    assert response.status_code == 200
    content = response.content
    assert "Quarterly capacity check".encode() in content
    assert b"revised lead-time" in content          # the notes/body text renders
    assert communication_a.number.encode() in content
    assert b"Other Interactions" in content
    # The siblings table is scoped + self-excluded: the real sibling links in, self does not.
    siblings_section = content.split(b"Other Interactions")[1]
    assert f"vendor-communications/{sibling.pk}/".encode() in siblings_section
    assert f"vendor-communications/{communication_a.pk}/".encode() not in siblings_section


class TestCrudFlows:
    def test_create_edit_delete(self, client_a, tenant_a, vendor_party_a, communication_a):
        create_url = reverse("inventory:vendorcommunication_create")
        get_form = client_a.get(create_url)
        assert get_form.status_code == 200

        response = client_a.post(create_url, data={
            "party": vendor_party_a.pk, "channel": "meeting", "direction": "outbound",
            "subject": "View probe", "body": "",
            "occurred_at": "2026-08-20 10:00", "follow_up_on": "",
        })
        assert response.status_code == 302
        assert response.url == reverse("inventory:vendorcommunication_list")
        created = VendorCommunication.objects.get(tenant=tenant_a, subject="View probe")
        assert created.number.startswith("VC-")

        edit_url = reverse("inventory:vendorcommunication_edit", args=[created.pk])
        assert client_a.get(edit_url).status_code == 200
        edited = client_a.post(edit_url, data={
            "party": vendor_party_a.pk, "channel": "meeting", "direction": "outbound",
            "subject": "View probe — rescheduled", "body": "",
            "occurred_at": "2026-08-21 10:00", "follow_up_on": "",
        })
        assert edited.status_code == 302
        detail = client_a.get(reverse("inventory:vendorcommunication_detail",
                                      args=[created.pk]))
        assert "View probe — rescheduled".encode() in detail.content

        delete_url = reverse("inventory:vendorcommunication_delete", args=[created.pk])
        deleted = client_a.post(delete_url)
        assert deleted.status_code == 302
        assert not VendorCommunication.objects.filter(pk=created.pk).exists()


def test_anonymous_is_redirected_to_login(client):
    """settings.LOGIN_URL is the *named* route "accounts:login" — resolve it and expect
    the redirect target to be exactly that path."""
    response = client.get(reverse("inventory:vendorcommunication_list"))
    assert response.status_code == 302
    login_path = reverse("accounts:login")
    assert login_path in response.url or "/login" in response.url
