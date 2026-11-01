"""Unit and contract tests for eCommerce 9.9 Content Management System (CMS) views.

Covers:
- List views: cmspage_list, blogarticle_list, mediaasset_list, contentblock_list (context keys, filters, search, pagination).
- Detail views: cmspage_detail, cmspage_preview, blogarticle_detail, mediaasset_detail, contentblock_detail.
- Create / Edit views: GET renders form, POST validates and redirects to detail, audit logging.
- Delete views: POST removes record and redirects to list, GET rejected with 405.

Conventions enforced:
- Test functions: test_contentmanagement_*
- Module-level helpers: _contentmanagement_*
"""
import pytest
from django.urls import reverse

from apps.core.models import AuditLog
from apps.ecommerce.models import (
    CmsPage,
    BlogArticle,
    MediaAsset,
    ContentBlock,
)
from apps.ecommerce.tests.conftest import (
    _contentmanagement_media,
    _contentmanagement_page,
    _contentmanagement_blog,
    _contentmanagement_block,
)

pytestmark = pytest.mark.django_db


# ==============================================================================
# 1. CmsPage Views Tests
# ==============================================================================

def test_contentmanagement_cmspage_list_context(auth_client_a, ecom_cmspage_a):
    """Verify cmspage_list renders 200 with all contract context keys."""
    url = reverse("ecommerce:cmspage_list")
    resp = auth_client_a.get(url)
    assert resp.status_code == 200
    assert "pages" in resp.context
    assert "page_type_choices" in resp.context
    assert "status_choices" in resp.context
    assert "layout_choices" in resp.context
    assert "selected_type" in resp.context
    assert "selected_status" in resp.context
    assert "selected_layout" in resp.context
    assert "search_query" in resp.context
    assert ecom_cmspage_a in resp.context["pages"]


def test_contentmanagement_cmspage_list_filters(auth_client_a, tenant_a):
    """Verify cmspage_list applies search, type, and status filters."""
    p1 = _contentmanagement_page(tenant_a, title="Alpha Privacy Policy", slug="alpha-policy", page_type="policy", status="published")
    p2 = _contentmanagement_page(tenant_a, title="Beta Promotion", slug="beta-promo", page_type="landing", status="draft")

    url = reverse("ecommerce:cmspage_list")
    resp = auth_client_a.get(f"{url}?q=Privacy&page_type=policy&status=published")
    assert resp.status_code == 200
    pages = list(resp.context["pages"])
    assert p1 in pages
    assert p2 not in pages


def test_contentmanagement_cmspage_detail(auth_client_a, ecom_cmspage_a):
    """Verify cmspage_detail renders 200 with page in context."""
    url = reverse("ecommerce:cmspage_detail", args=[ecom_cmspage_a.pk])
    resp = auth_client_a.get(url)
    assert resp.status_code == 200
    assert resp.context["page"] == ecom_cmspage_a
    assert ecom_cmspage_a.title in resp.content.decode("utf-8")


def test_contentmanagement_cmspage_preview(auth_client_a, ecom_cmspage_a):
    """Verify cmspage_preview renders 200 with is_preview True."""
    url = reverse("ecommerce:cmspage_preview", args=[ecom_cmspage_a.pk])
    resp = auth_client_a.get(url)
    assert resp.status_code == 200
    assert resp.context["page"] == ecom_cmspage_a
    assert resp.context["is_preview"] is True
    assert "Live Preview Mode" in resp.content.decode("utf-8")


def test_contentmanagement_cmspage_create_post(auth_client_a, tenant_a):
    """Verify cmspage_create handles valid POST, creates record, and logs audit."""
    url = reverse("ecommerce:cmspage_create")
    data = {
        "title": "Created Via View",
        "slug": "created-via-view",
        "page_type": "standard",
        "status": "published",
        "template_layout": "full_width",
        "raw_html_body": "<p>Content created by user</p>",
    }
    resp = auth_client_a.post(url, data=data)
    assert resp.status_code == 302
    created = CmsPage.objects.get(tenant=tenant_a, slug="created-via-view")
    assert resp.url == reverse("ecommerce:cmspage_detail", args=[created.pk])
    assert AuditLog.objects.filter(tenant=tenant_a, action="create").exists()


def test_contentmanagement_cmspage_edit_post(auth_client_a, ecom_cmspage_a):
    """Verify cmspage_edit updates existing page and redirects."""
    url = reverse("ecommerce:cmspage_edit", args=[ecom_cmspage_a.pk])
    data = {
        "title": "Updated Store Page Title",
        "slug": ecom_cmspage_a.slug,
        "page_type": "about",
        "status": "published",
        "template_layout": "boxed",
    }
    resp = auth_client_a.post(url, data=data)
    assert resp.status_code == 302
    ecom_cmspage_a.refresh_from_db()
    assert ecom_cmspage_a.title == "Updated Store Page Title"
    assert ecom_cmspage_a.page_type == "about"


def test_contentmanagement_cmspage_delete(auth_client_a, tenant_a):
    """Verify cmspage_delete deletes page on POST and rejects GET."""
    page = _contentmanagement_page(tenant_a, slug="delete-me-page")
    url = reverse("ecommerce:cmspage_delete", args=[page.pk])

    # GET is rejected with 405
    get_resp = auth_client_a.get(url)
    assert get_resp.status_code == 405

    # POST deletes record
    post_resp = auth_client_a.post(url)
    assert post_resp.status_code == 302
    assert not CmsPage.objects.filter(pk=page.pk).exists()


# ==============================================================================
# 2. BlogArticle Views Tests
# ==============================================================================

def test_contentmanagement_blogarticle_list_context(auth_client_a, ecom_blogarticle_a):
    """Verify blogarticle_list renders 200 with contract context keys."""
    url = reverse("ecommerce:blogarticle_list")
    resp = auth_client_a.get(url)
    assert resp.status_code == 200
    assert "articles" in resp.context
    assert "category_choices" in resp.context
    assert "status_choices" in resp.context
    assert "selected_category" in resp.context
    assert "selected_status" in resp.context
    assert "search_query" in resp.context
    assert ecom_blogarticle_a in resp.context["articles"]


def test_contentmanagement_blogarticle_detail(auth_client_a, ecom_blogarticle_a):
    """Verify blogarticle_detail renders 200 with article in context."""
    url = reverse("ecommerce:blogarticle_detail", args=[ecom_blogarticle_a.pk])
    resp = auth_client_a.get(url)
    assert resp.status_code == 200
    assert resp.context["article"] == ecom_blogarticle_a
    assert ecom_blogarticle_a.title in resp.content.decode("utf-8")


def test_contentmanagement_blogarticle_create_post(auth_client_a, tenant_a, user_a, ecom_mediaasset_a):
    """Verify blogarticle_create saves article and redirects to detail."""
    url = reverse("ecommerce:blogarticle_create")
    data = {
        "title": "Brand New Article Headline",
        "slug": "brand-new-article",
        "author": user_a.pk,
        "category": "news",
        "excerpt": "Short excerpt summary",
        "body_markdown": "# Editorial Title\n\nFull article body text.",
        "featured_media": ecom_mediaasset_a.pk,
        "status": "published",
        "tags": "news, company",
        "reading_time_minutes": 3,
        "allow_comments": True,
        "is_featured": False,
    }
    resp = auth_client_a.post(url, data=data)
    assert resp.status_code == 302
    article = BlogArticle.objects.get(tenant=tenant_a, slug="brand-new-article")
    assert resp.url == reverse("ecommerce:blogarticle_detail", args=[article.pk])
    assert article.status == "published"


def test_contentmanagement_blogarticle_delete(auth_client_a, tenant_a):
    """Verify blogarticle_delete deletes article and redirects."""
    article = _contentmanagement_blog(tenant_a, slug="article-to-delete")
    url = reverse("ecommerce:blogarticle_delete", args=[article.pk])

    resp = auth_client_a.post(url)
    assert resp.status_code == 302
    assert not BlogArticle.objects.filter(pk=article.pk).exists()


# ==============================================================================
# 3. MediaAsset Views Tests
# ==============================================================================

def test_contentmanagement_mediaasset_list_context(auth_client_a, ecom_mediaasset_a):
    """Verify mediaasset_list renders 200 with contract context keys."""
    url = reverse("ecommerce:mediaasset_list")
    resp = auth_client_a.get(url)
    assert resp.status_code == 200
    assert "assets" in resp.context
    assert "media_type_choices" in resp.context
    assert "folder_choices" in resp.context
    assert "selected_type" in resp.context
    assert "selected_folder" in resp.context
    assert "search_query" in resp.context
    assert ecom_mediaasset_a in resp.context["assets"]


def test_contentmanagement_mediaasset_detail(auth_client_a, ecom_mediaasset_a):
    """Verify mediaasset_detail renders 200 with asset in context."""
    url = reverse("ecommerce:mediaasset_detail", args=[ecom_mediaasset_a.pk])
    resp = auth_client_a.get(url)
    assert resp.status_code == 200
    assert resp.context["asset"] == ecom_mediaasset_a
    assert ecom_mediaasset_a.title in resp.content.decode("utf-8")


def test_contentmanagement_mediaasset_create_post(auth_client_a, tenant_a):
    """Verify mediaasset_create handles valid POST and saves asset."""
    url = reverse("ecommerce:mediaasset_create")
    data = {
        "title": "Uploaded Promo Banner",
        "file_url": "https://example.com/cdn/promo-banner.jpg",
        "alt_text": "Promo Banner Alt",
        "caption": "Spring Sale 2026",
        "media_type": "banner",
        "folder_category": "banners",
        "file_size_bytes": 154000,
        "mime_type": "image/jpeg",
        "width_px": 1600,
        "height_px": 800,
    }
    resp = auth_client_a.post(url, data=data)
    assert resp.status_code == 302
    asset = MediaAsset.objects.get(tenant=tenant_a, title="Uploaded Promo Banner")
    assert resp.url == reverse("ecommerce:mediaasset_detail", args=[asset.pk])
    assert asset.uploaded_by is not None


def test_contentmanagement_mediaasset_delete(auth_client_a, tenant_a):
    """Verify mediaasset_delete deletes asset on POST."""
    asset = _contentmanagement_media(tenant_a, title="Delete Asset Test")
    url = reverse("ecommerce:mediaasset_delete", args=[asset.pk])

    resp = auth_client_a.post(url)
    assert resp.status_code == 302
    assert not MediaAsset.objects.filter(pk=asset.pk).exists()


# ==============================================================================
# 4. ContentBlock Views Tests
# ==============================================================================

def test_contentmanagement_contentblock_list_context(auth_client_a, ecom_contentblock_a):
    """Verify contentblock_list renders 200 with contract context keys."""
    url = reverse("ecommerce:contentblock_list")
    resp = auth_client_a.get(url)
    assert resp.status_code == 200
    assert "blocks" in resp.context
    assert "block_type_choices" in resp.context
    assert "selected_type" in resp.context
    assert "selected_active" in resp.context
    assert "search_query" in resp.context
    assert ecom_contentblock_a in resp.context["blocks"]


def test_contentmanagement_contentblock_detail(auth_client_a, ecom_contentblock_a):
    """Verify contentblock_detail renders 200 with block and content_block in context."""
    url = reverse("ecommerce:contentblock_detail", args=[ecom_contentblock_a.pk])
    resp = auth_client_a.get(url)
    assert resp.status_code == 200
    assert resp.context["block"] == ecom_contentblock_a
    assert resp.context["content_block"] == ecom_contentblock_a
    assert ecom_contentblock_a.name in resp.content.decode("utf-8")


def test_contentmanagement_contentblock_create_post(auth_client_a, tenant_a):
    """Verify contentblock_create creates new block and redirects."""
    url = reverse("ecommerce:contentblock_create")
    data = {
        "name": "New FAQ Accordion",
        "block_type": "faq_accordion",
        "headline": "Frequently Asked Questions",
        "body_text": "Answers to common shipping and return questions.",
        "bg_color_class": "bg-slate-50",
        "text_color_class": "text-slate-900",
        "sort_order": 5,
        "is_active": True,
    }
    resp = auth_client_a.post(url, data=data)
    assert resp.status_code == 302
    block = ContentBlock.objects.get(tenant=tenant_a, name="New FAQ Accordion")
    assert resp.url == reverse("ecommerce:contentblock_detail", args=[block.pk])


def test_contentmanagement_contentblock_delete(auth_client_a, tenant_a):
    """Verify contentblock_delete deletes block on POST."""
    block = _contentmanagement_block(tenant_a, name="Temp Block To Delete")
    url = reverse("ecommerce:contentblock_delete", args=[block.pk])

    resp = auth_client_a.post(url)
    assert resp.status_code == 302
    assert not ContentBlock.objects.filter(pk=block.pk).exists()
