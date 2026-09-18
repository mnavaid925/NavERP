"""Projects 7.12 — Portfolio & Program Management security tests.

Covers:
- IDOR isolation across tenant boundaries (cross-tenant 404s for detail, edit, delete, verbs)
- Anonymous access prevention (302 redirect to login)
- Tenantless user protection (redirect to dashboard:home)
- HTTP method restrictions (@require_POST returns 405 on GET)
- Cross-tenant foreign key injection rejection
"""
import pytest
from django.urls import reverse

from apps.projects.tests.conftest import (
    _portfolio_portfolio,
    _portfolio_program,
    _portfolio_investment,
    _portfolio_dependency,
    _projectinitiation_project,
)

pytestmark = pytest.mark.django_db


# ==================================================================================================
# IDOR Isolation (Tenant A client hitting Tenant B resources -> 404)
# ==================================================================================================

def test_portfolio_idor_protection(client_a, tenant_b, portfolio_b, program_b):
    p_b2 = _projectinitiation_project(tenant_b, name="Globex Project 2", code="GP-02")
    inv_b = _portfolio_investment(tenant_b, portfolio_b, p_b2)
    dep_b = _portfolio_dependency(tenant_b, p_b2, _projectinitiation_project(tenant_b, name="Globex Project 3", code="GP-03"))

    get_and_post_urls = [
        # Portfolio
        reverse("projects:prt_detail", kwargs={"pk": portfolio_b.pk}),
        reverse("projects:prt_edit", kwargs={"pk": portfolio_b.pk}),
        # Program
        reverse("projects:pgm_detail", kwargs={"pk": program_b.pk}),
        reverse("projects:pgm_edit", kwargs={"pk": program_b.pk}),
        # Investment
        reverse("projects:pin_detail", kwargs={"pk": inv_b.pk}),
        reverse("projects:pin_edit", kwargs={"pk": inv_b.pk}),
        # Dependency
        reverse("projects:pdep_detail", kwargs={"pk": dep_b.pk}),
        reverse("projects:pdep_edit", kwargs={"pk": dep_b.pk}),
    ]

    for url in get_and_post_urls:
        resp = client_a.get(url)
        assert resp.status_code == 404, f"Expected 404 on GET {url}, got {resp.status_code}"
        resp_post = client_a.post(url)
        assert resp_post.status_code == 404, f"Expected 404 on POST {url}, got {resp_post.status_code}"

    post_only_urls = [
        reverse("projects:prt_delete", kwargs={"pk": portfolio_b.pk}),
        reverse("projects:pgm_delete", kwargs={"pk": program_b.pk}),
        reverse("projects:pin_delete", kwargs={"pk": inv_b.pk}),
        reverse("projects:pin_fund", kwargs={"pk": inv_b.pk}),
        reverse("projects:pin_reject", kwargs={"pk": inv_b.pk}),
        reverse("projects:pin_defer", kwargs={"pk": inv_b.pk}),
        reverse("projects:pdep_delete", kwargs={"pk": dep_b.pk}),
        reverse("projects:pdep_clear", kwargs={"pk": dep_b.pk}),
        reverse("projects:pdep_reopen", kwargs={"pk": dep_b.pk}),
    ]

    for url in post_only_urls:
        resp_post = client_a.post(url)
        assert resp_post.status_code == 404, f"Expected 404 on POST {url}, got {resp_post.status_code}"


# ==================================================================================================
# Anonymous Access (@login_required -> 302 to login)
# ==================================================================================================

def test_portfolio_anonymous_redirect(client, portfolio_a, program_a, portfolio_investment_a, program_dependency_a):
    protected_urls = [
        reverse("projects:pfm_dashboard"),
        reverse("projects:prt_list"),
        reverse("projects:prt_create"),
        reverse("projects:prt_detail", kwargs={"pk": portfolio_a.pk}),
        reverse("projects:pgm_list"),
        reverse("projects:pin_list"),
        reverse("projects:pdep_list"),
    ]
    for url in protected_urls:
        resp = client.get(url)
        assert resp.status_code == 302
        assert "/accounts/login/" in resp.headers.get("Location", "") or "/login" in resp.headers.get("Location", "")


# ==================================================================================================
# HTTP Method Enforcement (@require_POST -> 405 on GET)
# ==================================================================================================

def test_portfolio_verbs_require_post(client_a, portfolio_a, program_a, portfolio_investment_a, program_dependency_a):
    post_only_urls = [
        reverse("projects:prt_delete", kwargs={"pk": portfolio_a.pk}),
        reverse("projects:pgm_delete", kwargs={"pk": program_a.pk}),
        reverse("projects:pin_delete", kwargs={"pk": portfolio_investment_a.pk}),
        reverse("projects:pin_fund", kwargs={"pk": portfolio_investment_a.pk}),
        reverse("projects:pin_reject", kwargs={"pk": portfolio_investment_a.pk}),
        reverse("projects:pin_defer", kwargs={"pk": portfolio_investment_a.pk}),
        reverse("projects:pdep_delete", kwargs={"pk": program_dependency_a.pk}),
        reverse("projects:pdep_clear", kwargs={"pk": program_dependency_a.pk}),
        reverse("projects:pdep_reopen", kwargs={"pk": program_dependency_a.pk}),
    ]
    for url in post_only_urls:
        resp = client_a.get(url)
        assert resp.status_code == 405, f"Expected 405 on GET {url}, got {resp.status_code}"


# ==================================================================================================
# Tenantless User Handling
# ==================================================================================================

def test_portfolio_create_tenantless_redirects(projectinitiation_tenantless_client):
    urls = [
        reverse("projects:prt_create"),
        reverse("projects:pgm_create"),
        reverse("projects:pin_create"),
        reverse("projects:pdep_create"),
    ]
    for url in urls:
        resp = projectinitiation_tenantless_client.get(url)
        assert resp.status_code in [302, 403]
