"""Projects 7.13 — Agile & Scrum Management security tests.

Covers:
- Unauthenticated access redirects to login (302)
- Cross-tenant IDOR returns 404 (detail & edit views)
- POST-only verbs reject GET with 405 Method Not Allowed
- Multi-tenancy isolation (data never leaks across tenants)
"""
import pytest
from django.urls import reverse

from apps.projects.models import (
    Project,
    ProjectEpic,
    ProjectRelease,
    Sprint,
    SprintImpediment,
    SprintRetrospective,
)

pytestmark = pytest.mark.django_db


def _create_project(tenant, name="Agile Project"):
    p = Project(tenant=tenant, name=name, code="AGL", status="active")
    p.save()
    return p


def _create_sprint(tenant, project, name="Sprint 1"):
    s = Sprint(tenant=tenant, project=project, name=name)
    s.save()
    return s


def _create_epic(tenant, project, name="Epic 1"):
    e = ProjectEpic(tenant=tenant, project=project, name=name)
    e.save()
    return e


def _create_release(tenant, project, name="Release 1.0"):
    r = ProjectRelease(tenant=tenant, project=project, name=name, version_tag="v1.0")
    r.save()
    return r


# ==================================================================================================
# Unauthenticated Access
# ==================================================================================================

@pytest.mark.parametrize(
    "url_name",
    [
        "projects:spt_list",
        "projects:epc_list",
        "projects:rel_list",
        "projects:imp_list",
        "projects:ret_list",
        "projects:sprint_backlog",
        "projects:sprint_execution",
        "projects:release_roadmap",
        "projects:velocity_report",
    ],
)
def test_agile_unauthenticated_redirects_to_login(client, url_name):
    res = client.get(reverse(url_name))
    assert res.status_code == 302
    assert "/login/" in res.url


# ==================================================================================================
# Cross-Tenant IDOR Isolation (404)
# ==================================================================================================

def test_agile_sprint_cross_tenant_idor_404(client_a, tenant_b):
    p_b = _create_project(tenant_b, "Globex Project")
    s_b = _create_sprint(tenant_b, p_b, "Globex Sprint")

    # Client A should get 404 when accessing Tenant B's sprint
    res_detail = client_a.get(reverse("projects:spt_detail", args=[s_b.pk]))
    assert res_detail.status_code == 404

    res_edit = client_a.get(reverse("projects:spt_edit", args=[s_b.pk]))
    assert res_edit.status_code == 404


def test_agile_epic_cross_tenant_idor_404(client_a, tenant_b):
    p_b = _create_project(tenant_b, "Globex Project")
    e_b = _create_epic(tenant_b, p_b, "Globex Epic")

    res_detail = client_a.get(reverse("projects:epc_detail", args=[e_b.pk]))
    assert res_detail.status_code == 404


def test_agile_release_cross_tenant_idor_404(client_a, tenant_b):
    p_b = _create_project(tenant_b, "Globex Project")
    r_b = _create_release(tenant_b, p_b, "Globex Release")

    res_detail = client_a.get(reverse("projects:rel_detail", args=[r_b.pk]))
    assert res_detail.status_code == 404


def test_agile_impediment_cross_tenant_idor_404(client_a, tenant_b):
    p_b = _create_project(tenant_b, "Globex Project")
    s_b = _create_sprint(tenant_b, p_b)
    imp_b = SprintImpediment(tenant=tenant_b, sprint=s_b, title="Globex Blocker", description="Blocked")
    imp_b.save()

    res = client_a.get(reverse("projects:imp_detail", args=[imp_b.pk]))
    assert res.status_code == 404


# ==================================================================================================
# POST-Only Verbs Reject GET with 405
# ==================================================================================================

@pytest.mark.parametrize(
    "url_name",
    [
        "projects:spt_start",
        "projects:spt_complete",
        "projects:spt_cancel",
        "projects:rel_publish",
        "projects:imp_resolve",
        "projects:ret_open",
        "projects:ret_close",
    ],
)
def test_agile_verbs_reject_get(client_a, tenant_a, url_name):
    p = _create_project(tenant_a)
    s = _create_sprint(tenant_a, p)
    res = client_a.get(reverse(url_name, args=[s.pk]))
    assert res.status_code == 405
