"""Projects 7.14 Client & External Collaboration — SECURITY tests.
"""
from decimal import Decimal

import pytest
from django.test import Client
from django.urls import reverse

from apps.projects.tests.conftest import (
    _clientcollab_amendment,
    _clientcollab_approval_request,
    _clientcollab_client_invoice,
    _clientcollab_portal_access,
    _clientcollab_sow,
    _clientcollab_vendor_handoff,
)


# ==============================================================================================
# Anonymous Access Gated (Login Required)
# ==============================================================================================

def test_clientcollab_anonymous_redirected_to_login(
    tenant_a,
    clientcollab_project_a,
    clientcollab_client_org_a,
    clientcollab_vendor_org_a,
    clientcollab_contact_person_a,
):
    anon = Client()
    portal = _clientcollab_portal_access(tenant_a, clientcollab_project_a, clientcollab_contact_person_a)
    approval = _clientcollab_approval_request(tenant_a, clientcollab_project_a)
    sow = _clientcollab_sow(tenant_a, clientcollab_project_a, clientcollab_client_org_a)
    handoff = _clientcollab_vendor_handoff(tenant_a, clientcollab_project_a, clientcollab_vendor_org_a)
    invoice = _clientcollab_client_invoice(tenant_a, clientcollab_project_a)

    routes = [
        reverse("projects:cpa_list"),
        reverse("projects:cpa_create"),
        reverse("projects:cpa_detail", args=[portal.pk]),
        reverse("projects:cpa_edit", args=[portal.pk]),
        reverse("projects:cfb_list"),
        reverse("projects:cfb_create"),
        reverse("projects:cfb_detail", args=[approval.pk]),
        reverse("projects:cfb_edit", args=[approval.pk]),
        reverse("projects:sow_list"),
        reverse("projects:sow_create"),
        reverse("projects:sow_detail", args=[sow.pk]),
        reverse("projects:sow_edit", args=[sow.pk]),
        reverse("projects:vhd_list"),
        reverse("projects:vhd_create"),
        reverse("projects:vhd_detail", args=[handoff.pk]),
        reverse("projects:vhd_edit", args=[handoff.pk]),
        reverse("projects:pci_list"),
        reverse("projects:pci_create"),
        reverse("projects:pci_detail", args=[invoice.pk]),
        reverse("projects:pci_edit", args=[invoice.pk]),
    ]

    for url in routes:
        resp = anon.get(url)
        assert resp.status_code == 302, f"Expected 302 redirect for anon on {url}, got {resp.status_code}"
        assert "/login/" in resp["Location"]


# ==============================================================================================
# Cross-Tenant IDOR Protection (Tenant B records unreachable by Tenant A)
# ==============================================================================================

def test_clientcollab_cross_tenant_idor_protection(
    client_a,
    tenant_b,
    clientcollab_project_b,
    clientcollab_client_org_b,
    clientcollab_vendor_org_b,
    clientcollab_contact_person_b,
):
    portal_b = _clientcollab_portal_access(tenant_b, clientcollab_project_b, clientcollab_contact_person_b)
    approval_b = _clientcollab_approval_request(tenant_b, clientcollab_project_b)
    sow_b = _clientcollab_sow(tenant_b, clientcollab_project_b, clientcollab_client_org_b)
    handoff_b = _clientcollab_vendor_handoff(tenant_b, clientcollab_project_b, clientcollab_vendor_org_b)
    invoice_b = _clientcollab_client_invoice(tenant_b, clientcollab_project_b)

    # Tenant A client attempting to access Tenant B objects must get 404
    get_404_routes = [
        reverse("projects:cpa_detail", args=[portal_b.pk]),
        reverse("projects:cpa_edit", args=[portal_b.pk]),
        reverse("projects:cfb_detail", args=[approval_b.pk]),
        reverse("projects:cfb_edit", args=[approval_b.pk]),
        reverse("projects:sow_detail", args=[sow_b.pk]),
        reverse("projects:sow_edit", args=[sow_b.pk]),
        reverse("projects:sow_amendment_create", args=[sow_b.pk]),
        reverse("projects:vhd_detail", args=[handoff_b.pk]),
        reverse("projects:vhd_edit", args=[handoff_b.pk]),
        reverse("projects:pci_detail", args=[invoice_b.pk]),
        reverse("projects:pci_edit", args=[invoice_b.pk]),
    ]

    for url in get_404_routes:
        resp = client_a.get(url)
        assert resp.status_code == 404, f"Cross-tenant GET on {url} returned {resp.status_code}, expected 404"

    # POST verbs across tenants must also return 404
    post_404_routes = [
        reverse("projects:cpa_delete", args=[portal_b.pk]),
        reverse("projects:cfb_delete", args=[approval_b.pk]),
        reverse("projects:cfb_approve", args=[approval_b.pk]),
        reverse("projects:cfb_reject", args=[approval_b.pk]),
        reverse("projects:sow_delete", args=[sow_b.pk]),
        reverse("projects:sow_activate", args=[sow_b.pk]),
        reverse("projects:vhd_delete", args=[handoff_b.pk]),
        reverse("projects:vhd_accept", args=[handoff_b.pk]),
        reverse("projects:vhd_reject", args=[handoff_b.pk]),
        reverse("projects:pci_delete", args=[invoice_b.pk]),
        reverse("projects:pci_generate_invoice", args=[invoice_b.pk]),
    ]

    for url in post_404_routes:
        resp = client_a.post(url, {})
        assert resp.status_code == 404, f"Cross-tenant POST on {url} returned {resp.status_code}, expected 404"


# ==============================================================================================
# Cross-Tenant List Queryset Isolation
# ==============================================================================================

def test_clientcollab_cross_tenant_list_isolation(
    client_a,
    client_b,
    tenant_a,
    tenant_b,
    clientcollab_project_a,
    clientcollab_project_b,
    clientcollab_client_org_a,
    clientcollab_client_org_b,
    clientcollab_vendor_org_a,
    clientcollab_vendor_org_b,
    clientcollab_contact_person_a,
    clientcollab_contact_person_b,
):
    portal_a = _clientcollab_portal_access(tenant_a, clientcollab_project_a, clientcollab_contact_person_a)
    portal_b = _clientcollab_portal_access(tenant_b, clientcollab_project_b, clientcollab_contact_person_b)

    sow_a = _clientcollab_sow(tenant_a, clientcollab_project_a, clientcollab_client_org_a, title="Tenant A SOW")
    sow_b = _clientcollab_sow(tenant_b, clientcollab_project_b, clientcollab_client_org_b, title="Tenant B SOW")

    # Client A list view
    r = client_a.get(reverse("projects:cpa_list"))
    assert r.status_code == 200
    assert clientcollab_contact_person_a.name.encode() in r.content
    assert clientcollab_contact_person_b.name.encode() not in r.content

    r = client_a.get(reverse("projects:sow_list"))
    assert r.status_code == 200
    assert b"Tenant A SOW" in r.content
    assert b"Tenant B SOW" not in r.content

    # Client B list view
    r = client_b.get(reverse("projects:sow_list"))
    assert r.status_code == 200
    assert b"Tenant B SOW" in r.content
    assert b"Tenant A SOW" not in r.content


# ==============================================================================================
# POST-Only Verbs Reject GET with 405
# ==============================================================================================

def test_clientcollab_verbs_reject_get_with_405(
    client_a,
    tenant_a,
    clientcollab_project_a,
    clientcollab_client_org_a,
    clientcollab_vendor_org_a,
):
    approval = _clientcollab_approval_request(tenant_a, clientcollab_project_a)
    sow = _clientcollab_sow(tenant_a, clientcollab_project_a, clientcollab_client_org_a)
    handoff = _clientcollab_vendor_handoff(tenant_a, clientcollab_project_a, clientcollab_vendor_org_a)
    invoice = _clientcollab_client_invoice(tenant_a, clientcollab_project_a)

    post_only_urls = [
        reverse("projects:cfb_approve", args=[approval.pk]),
        reverse("projects:cfb_reject", args=[approval.pk]),
        reverse("projects:sow_activate", args=[sow.pk]),
        reverse("projects:vhd_accept", args=[handoff.pk]),
        reverse("projects:vhd_reject", args=[handoff.pk]),
        reverse("projects:pci_generate_invoice", args=[invoice.pk]),
    ]

    for url in post_only_urls:
        resp = client_a.get(url)
        assert resp.status_code == 405, f"Expected 405 on GET {url}, got {resp.status_code}"
