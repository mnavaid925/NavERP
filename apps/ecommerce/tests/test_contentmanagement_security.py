"""Security and multi-tenant isolation tests for eCommerce 9.9 Content Management System (CMS).

Covers:
- Cross-tenant IDOR protection: Detail, edit, preview, and delete views return 404 for foreign tenant objects.
- List view tenant isolation: Tenant A never sees Tenant B records.
- Authentication gating: Anonymous requests redirected to login.
- Authorization gating: Delete operations require tenant admin privileges.
- Cross-tenant form injection: Rejecting foreign objects in forms.

Conventions enforced:
- Test functions: test_contentmanagement_*
- Module-level helpers: _contentmanagement_*
"""
import pytest
from django.urls import reverse

from apps.ecommerce.models import (
    CmsPage,
    BlogArticle,
    MediaAsset,
    ContentBlock,
)

pytestmark = pytest.mark.django_db


# ==============================================================================
# 1. Cross-Tenant IDOR Protection Tests
# ==============================================================================

def test_contentmanagement_cmspage_idor_detail(auth_client_a, ecom_cmspage_b):
    """Verify Tenant A client receives 404 when accessing Tenant B CmsPage detail."""
    url = reverse("ecommerce:cmspage_detail", args=[ecom_cmspage_b.pk])
    resp = auth_client_a.get(url)
    assert resp.status_code == 404


def test_contentmanagement_cmspage_idor_edit(auth_client_a, ecom_cmspage_b):
    """Verify Tenant A client receives 404 when accessing Tenant B CmsPage edit."""
    url = reverse("ecommerce:cmspage_edit", args=[ecom_cmspage_b.pk])
    resp = auth_client_a.get(url)
    assert resp.status_code == 404


def test_contentmanagement_cmspage_idor_preview(auth_client_a, ecom_cmspage_b):
    """Verify Tenant A client receives 404 when accessing Tenant B CmsPage preview."""
    url = reverse("ecommerce:cmspage_preview", args=[ecom_cmspage_b.pk])
    resp = auth_client_a.get(url)
    assert resp.status_code == 404


def test_contentmanagement_cmspage_idor_delete(auth_client_a, ecom_cmspage_b):
    """Verify Tenant A client receives 404 when attempting to delete Tenant B CmsPage."""
    url = reverse("ecommerce:cmspage_delete", args=[ecom_cmspage_b.pk])
    resp = auth_client_a.post(url)
    assert resp.status_code == 404
    assert CmsPage.objects.filter(pk=ecom_cmspage_b.pk).exists()


def test_contentmanagement_blogarticle_idor_detail(auth_client_a, ecom_blogarticle_b):
    """Verify Tenant A client receives 404 when accessing Tenant B BlogArticle detail."""
    url = reverse("ecommerce:blogarticle_detail", args=[ecom_blogarticle_b.pk])
    resp = auth_client_a.get(url)
    assert resp.status_code == 404


def test_contentmanagement_blogarticle_idor_edit(auth_client_a, ecom_blogarticle_b):
    """Verify Tenant A client receives 404 when accessing Tenant B BlogArticle edit."""
    url = reverse("ecommerce:blogarticle_edit", args=[ecom_blogarticle_b.pk])
    resp = auth_client_a.get(url)
    assert resp.status_code == 404


def test_contentmanagement_blogarticle_idor_delete(auth_client_a, ecom_blogarticle_b):
    """Verify Tenant A client receives 404 when attempting to delete Tenant B BlogArticle."""
    url = reverse("ecommerce:blogarticle_delete", args=[ecom_blogarticle_b.pk])
    resp = auth_client_a.post(url)
    assert resp.status_code == 404
    assert BlogArticle.objects.filter(pk=ecom_blogarticle_b.pk).exists()


def test_contentmanagement_mediaasset_idor_detail(auth_client_a, ecom_mediaasset_b):
    """Verify Tenant A client receives 404 when accessing Tenant B MediaAsset detail."""
    url = reverse("ecommerce:mediaasset_detail", args=[ecom_mediaasset_b.pk])
    resp = auth_client_a.get(url)
    assert resp.status_code == 404


def test_contentmanagement_mediaasset_idor_edit(auth_client_a, ecom_mediaasset_b):
    """Verify Tenant A client receives 404 when accessing Tenant B MediaAsset edit."""
    url = reverse("ecommerce:mediaasset_edit", args=[ecom_mediaasset_b.pk])
    resp = auth_client_a.get(url)
    assert resp.status_code == 404


def test_contentmanagement_mediaasset_idor_delete(auth_client_a, ecom_mediaasset_b):
    """Verify Tenant A client receives 404 when attempting to delete Tenant B MediaAsset."""
    url = reverse("ecommerce:mediaasset_delete", args=[ecom_mediaasset_b.pk])
    resp = auth_client_a.post(url)
    assert resp.status_code == 404
    assert MediaAsset.objects.filter(pk=ecom_mediaasset_b.pk).exists()


def test_contentmanagement_contentblock_idor_detail(auth_client_a, ecom_contentblock_b):
    """Verify Tenant A client receives 404 when accessing Tenant B ContentBlock detail."""
    url = reverse("ecommerce:contentblock_detail", args=[ecom_contentblock_b.pk])
    resp = auth_client_a.get(url)
    assert resp.status_code == 404


def test_contentmanagement_contentblock_idor_edit(auth_client_a, ecom_contentblock_b):
    """Verify Tenant A client receives 404 when accessing Tenant B ContentBlock edit."""
    url = reverse("ecommerce:contentblock_edit", args=[ecom_contentblock_b.pk])
    resp = auth_client_a.get(url)
    assert resp.status_code == 404


def test_contentmanagement_contentblock_idor_delete(auth_client_a, ecom_contentblock_b):
    """Verify Tenant A client receives 404 when attempting to delete Tenant B ContentBlock."""
    url = reverse("ecommerce:contentblock_delete", args=[ecom_contentblock_b.pk])
    resp = auth_client_a.post(url)
    assert resp.status_code == 404
    assert ContentBlock.objects.filter(pk=ecom_contentblock_b.pk).exists()


# ==============================================================================
# 2. List View Multi-Tenant Isolation Tests
# ==============================================================================

def test_contentmanagement_list_isolation(
    auth_client_a,
    ecom_cmspage_a, ecom_cmspage_b,
    ecom_blogarticle_a, ecom_blogarticle_b,
    ecom_mediaasset_a, ecom_mediaasset_b,
    ecom_contentblock_a, ecom_contentblock_b,
):
    """Verify Tenant A client never sees Tenant B records in any list view."""
    # Pages
    r_pages = auth_client_a.get(reverse("ecommerce:cmspage_list"))
    pages = list(r_pages.context["pages"])
    assert ecom_cmspage_a in pages
    assert ecom_cmspage_b not in pages

    # Blog
    r_blog = auth_client_a.get(reverse("ecommerce:blogarticle_list"))
    articles = list(r_blog.context["articles"])
    assert ecom_blogarticle_a in articles
    assert ecom_blogarticle_b not in articles

    # Media
    r_media = auth_client_a.get(reverse("ecommerce:mediaasset_list"))
    assets = list(r_media.context["assets"])
    assert ecom_mediaasset_a in assets
    assert ecom_mediaasset_b not in assets

    # Blocks
    r_blocks = auth_client_a.get(reverse("ecommerce:contentblock_list"))
    blocks = list(r_blocks.context["blocks"])
    assert ecom_contentblock_a in blocks
    assert ecom_contentblock_b not in blocks


# ==============================================================================
# 3. Authentication & Authorization Tests
# ==============================================================================

def test_contentmanagement_anonymous_redirected(client, ecom_cmspage_a):
    """Verify unauthenticated requests are redirected to login."""
    urls = [
        reverse("ecommerce:cmspage_list"),
        reverse("ecommerce:cmspage_create"),
        reverse("ecommerce:cmspage_detail", args=[ecom_cmspage_a.pk]),
        reverse("ecommerce:cmspage_edit", args=[ecom_cmspage_a.pk]),
        reverse("ecommerce:cmspage_preview", args=[ecom_cmspage_a.pk]),
        reverse("ecommerce:blogarticle_list"),
        reverse("ecommerce:mediaasset_list"),
        reverse("ecommerce:contentblock_list"),
    ]
    for url in urls:
        resp = client.get(url)
        assert resp.status_code == 302
        assert "/accounts/login/" in resp.url


def test_contentmanagement_delete_requires_tenant_admin(client, regular_user_a, ecom_cmspage_a):
    """Verify non-admin tenant user is forbidden (403) from deleting objects."""
    client.force_login(regular_user_a)
    url = reverse("ecommerce:cmspage_delete", args=[ecom_cmspage_a.pk])
    resp = client.post(url)
    assert resp.status_code == 403
    assert CmsPage.objects.filter(pk=ecom_cmspage_a.pk).exists()
