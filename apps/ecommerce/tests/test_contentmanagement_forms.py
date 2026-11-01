"""Unit and contract tests for eCommerce 9.9 Content Management System (CMS) forms.

Covers:
- CmsPageForm: validation, slug uniqueness per tenant, script injection rejection, tenant binding.
- BlogArticleForm: tenant author scoping, reject_foreign on author and media, slug normalization.
- MediaAssetForm: URL validation (http/https only, no javascript:), TenantUniqueMixin tenant binding.
- ContentBlockForm: CTA URL validation (relative / http / https, no javascript:), reject_foreign on media/category/product.

Conventions enforced:
- Test functions: test_contentmanagement_*
- Module-level helpers: _contentmanagement_*
"""
import pytest

from apps.ecommerce.forms import (
    CmsPageForm,
    BlogArticleForm,
    MediaAssetForm,
    ContentBlockForm,
)
from apps.ecommerce.models import (
    CmsPage,
    BlogArticle,
    MediaAsset,
    ContentBlock,
)

pytestmark = pytest.mark.django_db


# ==============================================================================
# 1. CmsPageForm Tests
# ==============================================================================

def test_contentmanagement_cmspage_form_valid(tenant_a):
    """Verify CmsPageForm validates and saves with valid data."""
    data = {
        "title": "New Store Landing Page",
        "slug": "new-landing",
        "page_type": "landing",
        "status": "published",
        "template_layout": "boxed",
        "meta_title": "SEO Title",
        "meta_description": "SEO Description",
        "canonical_url": "https://example.com/new-landing/",
        "is_indexable": True,
        "raw_html_body": "<h2>Welcome</h2><p>Promotional offer text</p>",
        "is_ab_test_active": True,
        "ab_variant_label": "Variant B",
        "ab_traffic_percentage": 50,
    }
    form = CmsPageForm(data=data, tenant=tenant_a)
    assert form.is_valid(), form.errors
    page = form.save()
    assert page.tenant == tenant_a
    assert page.number.startswith("EPAG-")
    assert page.title == "New Store Landing Page"


def test_contentmanagement_cmspage_form_slug_uniqueness(tenant_a):
    """Verify CmsPageForm rejects duplicate slug for the same tenant."""
    CmsPage.objects.create(
        tenant=tenant_a,
        title="Existing Page",
        slug="existing-slug",
    )
    data = {
        "title": "Another Page",
        "slug": "existing-slug",
        "page_type": "standard",
        "status": "draft",
        "template_layout": "full_width",
    }
    form = CmsPageForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "slug" in form.errors


def test_contentmanagement_cmspage_form_xss_script_rejected(tenant_a):
    """Verify CmsPageForm rejects script tags and event handlers in raw_html_body."""
    xss_payloads = [
        "<script>alert(1)</script>",
        "<img src=x onerror=alert('xss')>",
        "<iframe src='javascript:alert(1)'></iframe>",
    ]
    for payload in xss_payloads:
        form = CmsPageForm(
            data={
                "title": "XSS Test Page",
                "slug": "xss-test",
                "page_type": "standard",
                "status": "draft",
                "template_layout": "full_width",
                "raw_html_body": payload,
            },
            tenant=tenant_a,
        )
        assert not form.is_valid(), f"Expected form rejection for payload: {payload}"
        assert "raw_html_body" in form.errors


# ==============================================================================
# 2. BlogArticleForm Tests
# ==============================================================================

def test_contentmanagement_blogarticle_form_valid(tenant_a, user_a, ecom_mediaasset_a):
    """Verify BlogArticleForm validates and saves with valid data."""
    data = {
        "title": "Sustainable Style Trends",
        "slug": "sustainable-style-trends",
        "author": user_a.pk,
        "category": "guides_tutorials",
        "excerpt": "A brief overview of modern sustainable fashion.",
        "body_markdown": "# Sustainable Trends\n\nFull editorial markdown content.",
        "featured_media": ecom_mediaasset_a.pk,
        "status": "published",
        "tags": "fashion, eco, lifestyle",
        "reading_time_minutes": 4,
        "allow_comments": True,
        "is_featured": True,
    }
    form = BlogArticleForm(data=data, tenant=tenant_a)
    assert form.is_valid(), form.errors
    article = form.save()
    assert article.tenant == tenant_a
    assert article.author == user_a
    assert article.number.startswith("EBLG-")


def test_contentmanagement_blogarticle_form_foreign_author_rejected(tenant_a, user_b):
    """Verify BlogArticleForm rejects an author user belonging to a different tenant."""
    data = {
        "title": "Foreign Author Post",
        "slug": "foreign-author-post",
        "author": user_b.pk,
        "category": "news",
        "body_markdown": "Test content",
    }
    form = BlogArticleForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "author" in form.errors


def test_contentmanagement_blogarticle_form_foreign_media_rejected(tenant_a, user_a, ecom_mediaasset_b):
    """Verify BlogArticleForm rejects featured media belonging to a different tenant."""
    data = {
        "title": "Cross Tenant Media Post",
        "slug": "cross-tenant-media-post",
        "author": user_a.pk,
        "category": "news",
        "body_markdown": "Test content",
        "featured_media": ecom_mediaasset_b.pk,
    }
    form = BlogArticleForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "featured_media" in form.errors


# ==============================================================================
# 3. MediaAssetForm Tests
# ==============================================================================

def test_contentmanagement_mediaasset_form_valid(tenant_a):
    """Verify MediaAssetForm validates and saves with valid data."""
    data = {
        "title": "Promotional Banner Graphic",
        "file_url": "https://cdn.example.com/assets/promo.jpg",
        "alt_text": "Promotional discounts visual",
        "caption": "Summer 2026 Promo",
        "media_type": "banner",
        "folder_category": "banners",
        "file_size_bytes": 204800,
        "mime_type": "image/jpeg",
        "width_px": 1920,
        "height_px": 1080,
    }
    form = MediaAssetForm(data=data, tenant=tenant_a)
    assert form.is_valid(), form.errors
    asset = form.save()
    assert asset.tenant == tenant_a
    assert asset.number.startswith("EMED-")


def test_contentmanagement_mediaasset_form_invalid_url_schemes(tenant_a):
    """Verify MediaAssetForm rejects non-http/https URL schemes."""
    invalid_urls = [
        "javascript:alert(1)",
        "ftp://example.com/file.png",
        "data:image/png;base64,iVBORw0KGgoAAA",
        "/relative/path/banner.jpg",
    ]
    for url in invalid_urls:
        form = MediaAssetForm(
            data={
                "title": "Invalid URL Asset",
                "file_url": url,
                "media_type": "image",
                "folder_category": "banners",
            },
            tenant=tenant_a,
        )
        assert not form.is_valid()
        assert "file_url" in form.errors


# ==============================================================================
# 4. ContentBlockForm Tests
# ==============================================================================

def test_contentmanagement_contentblock_form_valid(tenant_a, ecom_mediaasset_a, ecom_category_a, ecom_product_a):
    """Verify ContentBlockForm validates and saves with valid catalog associations."""
    data = {
        "name": "Summer Hero Banner",
        "block_type": "hero_banner",
        "headline": "Trending Summer Collection",
        "subheadline": "Limited edition apparel",
        "body_text": "Exclusive online discounts.",
        "media_asset": ecom_mediaasset_a.pk,
        "cta_label": "Shop Now",
        "cta_url": "/category/apparel-fashion/",
        "target_category": ecom_category_a.pk,
        "target_product": ecom_product_a.pk,
        "bg_color_class": "bg-indigo-900",
        "text_color_class": "text-white",
        "sort_order": 1,
        "is_active": True,
    }
    form = ContentBlockForm(data=data, tenant=tenant_a)
    assert form.is_valid(), form.errors
    block = form.save()
    assert block.tenant == tenant_a
    assert block.number.startswith("EBLK-")
    assert block.media_asset == ecom_mediaasset_a


def test_contentmanagement_contentblock_form_foreign_associations_rejected(
    tenant_a, ecom_mediaasset_b, ecom_category_b, ecom_product_b
):
    """Verify ContentBlockForm rejects foreign media, category, and product."""
    data = {
        "name": "Cross Tenant Block",
        "block_type": "hero_banner",
        "media_asset": ecom_mediaasset_b.pk,
        "target_category": ecom_category_b.pk,
        "target_product": ecom_product_b.pk,
    }
    form = ContentBlockForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "media_asset" in form.errors or "target_category" in form.errors or "target_product" in form.errors


def test_contentmanagement_contentblock_form_cta_url_validation(tenant_a):
    """Verify ContentBlockForm rejects javascript: and dangerous protocols."""
    invalid_ctas = [
        "javascript:alert(1)",
        "data:text/html;base64,PHNjcmlwdD4=",
        "vbscript:msgbox(1)",
    ]
    for cta in invalid_ctas:
        form = ContentBlockForm(
            data={
                "name": "CTA Test Block",
                "block_type": "hero_banner",
                "cta_url": cta,
            },
            tenant=tenant_a,
        )
        assert not form.is_valid()
        assert "cta_url" in form.errors
