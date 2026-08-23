"""Inventory 5.10 Returns Management — view integration tests."""
from decimal import Decimal

import pytest
from django.urls import reverse

from apps.inventory.models import DispositionRoutingRule, ReturnInspection

pytestmark = pytest.mark.django_db


def test_returninspection_list_view(client_a, inspection_a):
    """List view renders 200 with inspection and KPI counts."""
    url = reverse("inventory:returninspection_list")
    resp = client_a.get(url)
    assert resp.status_code == 200
    assert inspection_a.number in resp.content.decode()


def test_returninspection_detail_view(client_a, inspection_a):
    """Detail view renders 200 and includes routing recommendation section."""
    url = reverse("inventory:returninspection_detail", kwargs={"pk": inspection_a.pk})
    resp = client_a.get(url)
    assert resp.status_code == 200
    assert inspection_a.number in resp.content.decode()
    assert "Disposition Routing Engine" in resp.content.decode()


def test_dispositionrule_list_view(client_a, disposition_rule_a):
    """Disposition rules list view renders 200 with active rules."""
    url = reverse("inventory:dispositionrule_list")
    resp = client_a.get(url)
    assert resp.status_code == 200
    assert disposition_rule_a.name in resp.content.decode()


def test_returns_workbench_view(client_a, rma_a, inspection_a):
    """Workbench view renders 200 with open returns and bench summary."""
    url = reverse("inventory:returns_workbench")
    resp = client_a.get(url)
    assert resp.status_code == 200
    assert "Warehouse Returns Workbench" in resp.content.decode()
    assert rma_a.number in resp.content.decode()
