"""Unit and contract tests for eCommerce 9.9 Content Management System (CMS) models.

Covers:
- CmsPage: prefix EPAG-, SEO metadata fields, A/B testing settings, constraints, layout choices.
- BlogArticle: prefix EBLG-, auto-slugification, published_at auto-timestamping, tag_list property, author FK, constraints.
- MediaAsset: prefix EMED-, asset URL, dimensions, file size, MIME type, folder category choices.
- ContentBlock: prefix EBLK-, sort order, block types, associated media/category/product links, style classes.

Conventions enforced:
- Test functions: test_contentmanagement_*
- Module-level helpers: _contentmanagement_*
"""
import pytest
from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.ecommerce.models import (
    CmsPage,
    BlogArticle,
    MediaAsset,
    ContentBlock,
)
from apps.ecommerce.tests.conftest import (
    CONTENTMANAGEMENT_MODEL_FIELDS,
    CONTENTMANAGEMENT_CHOICES,
    _contentmanagement_media,
    _contentmanagement_page,
    _contentmanagement_blog,
    _contentmanagement_block,
)

pytestmark = pytest.mark.django_db


# ==============================================================================
# 1. Contract Fields & Choices Verification
# ==============================================================================

def test_contentmanagement_model_fields_contract():
    """Verify that models define every expected contract field."""
    for model_name, expected_fields in CONTENTMANAGEMENT_MODEL_FIELDS.items():
        model_cls = {
            "CmsPage": CmsPage,
            "BlogArticle": BlogArticle,
            "MediaAsset": MediaAsset,
            "ContentBlock": ContentBlock,
        }[model_name]
        actual_fields = {f.name for f in model_cls._meta.get_fields()}
        for expected in expected_fields:
            assert expected in actual_fields, f"Field '{expected}' missing from {model_name}"


def test_contentmanagement_choices_contract():
    """Verify choices match the contract choices."""
    assert dict(CmsPage.PAGE_TYPE_CHOICES) == dict(CONTENTMANAGEMENT_CHOICES["CmsPage"]["page_type"])
    assert dict(CmsPage.STATUS_CHOICES) == dict(CONTENTMANAGEMENT_CHOICES["CmsPage"]["status"])
    assert dict(CmsPage.LAYOUT_CHOICES) == dict(CONTENTMANAGEMENT_CHOICES["CmsPage"]["template_layout"])
    assert dict(BlogArticle.CATEGORY_CHOICES) == dict(CONTENTMANAGEMENT_CHOICES["BlogArticle"]["category"])
    assert dict(BlogArticle.STATUS_CHOICES) == dict(CONTENTMANAGEMENT_CHOICES["BlogArticle"]["status"])
    assert dict(MediaAsset.MEDIA_TYPE_CHOICES) == dict(CONTENTMANAGEMENT_CHOICES["MediaAsset"]["media_type"])
    assert dict(MediaAsset.FOLDER_CHOICES) == dict(CONTENTMANAGEMENT_CHOICES["MediaAsset"]["folder_category"])
    assert dict(ContentBlock.BLOCK_TYPE_CHOICES) == dict(CONTENTMANAGEMENT_CHOICES["ContentBlock"]["block_type"])


# ==============================================================================
# 2. CmsPage Model Tests
# ==============================================================================

def test_contentmanagement_cmspage_number_generation(tenant_a):
    """Verify CmsPage auto-generates sequential EPAG- numbers."""
    page1 = _contentmanagement_page(tenant_a, slug="page-one", title="Page One")
    page2 = _contentmanagement_page(tenant_a, slug="page-two", title="Page Two")
    assert page1.number.startswith("EPAG-")
    assert page2.number.startswith("EPAG-")
    assert page1.number != page2.number


def test_contentmanagement_cmspage_str(tenant_a):
    """Verify CmsPage __str__ contains number and title."""
    page = _contentmanagement_page(tenant_a, title="About Our Store", slug="about-test")
    assert page.number in str(page)
    assert "About Our Store" in str(page)


def test_contentmanagement_cmspage_ab_testing_defaults(tenant_a):
    """Verify A/B testing fields default correctly."""
    page = _contentmanagement_page(tenant_a, slug="ab-test-page")
    assert page.is_ab_test_active is False
    assert page.ab_traffic_percentage == 50
    assert page.ab_variant_label == ""


def test_contentmanagement_cmspage_slug_unique_per_tenant(tenant_a):
    """Verify duplicate slug within same tenant raises IntegrityError."""
    _contentmanagement_page(tenant_a, slug="duplicate-slug", title="First")
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            _contentmanagement_page(tenant_a, slug="duplicate-slug", title="Second")


def test_contentmanagement_cmspage_same_slug_different_tenant(tenant_a, tenant_b):
    """Verify different tenants can use identical slug."""
    p_a = _contentmanagement_page(tenant_a, slug="shared-slug", title="Tenant A")
    p_b = _contentmanagement_page(tenant_b, slug="shared-slug", title="Tenant B")
    assert p_a.slug == p_b.slug
    assert p_a.tenant != p_b.tenant


# ==============================================================================
# 3. BlogArticle Model Tests
# ==============================================================================

def test_contentmanagement_blogarticle_number_generation(tenant_a):
    """Verify BlogArticle auto-generates sequential EBLG- numbers."""
    art1 = _contentmanagement_blog(tenant_a, slug="post-one", title="Post One")
    art2 = _contentmanagement_blog(tenant_a, slug="post-two", title="Post Two")
    assert art1.number.startswith("EBLG-")
    assert art2.number.startswith("EBLG-")
    assert art1.number != art2.number


def test_contentmanagement_blogarticle_auto_slug(tenant_a):
    """Verify BlogArticle auto-slugifies title if slug is empty."""
    art = BlogArticle.objects.create(
        tenant=tenant_a,
        title="Automated Headline For Testing",
        excerpt="Summary snippet",
        body_markdown="Content here",
    )
    assert art.slug == "automated-headline-for-testing"


def test_contentmanagement_blogarticle_published_at_auto_set(tenant_a):
    """Verify published_at is automatically populated when status is published."""
    art = _contentmanagement_blog(
        tenant_a,
        slug="auto-publish-test",
        status="published",
        published_at=None,
    )
    assert art.published_at is not None
    assert art.published_at <= timezone.now()


def test_contentmanagement_blogarticle_tag_list_property(tenant_a):
    """Verify tag_list property parses comma-separated tags into stripped list."""
    art = _contentmanagement_blog(
        tenant_a,
        slug="tags-test",
        tags="  fashion, lifestyle , sustainable, , eco  ",
    )
    assert art.tag_list == ["fashion", "lifestyle", "sustainable", "eco"]


def test_contentmanagement_blogarticle_empty_tags_property(tenant_a):
    """Verify tag_list property handles blank/empty tags gracefully."""
    art = _contentmanagement_blog(tenant_a, slug="no-tags-test", tags="")
    assert art.tag_list == []


# ==============================================================================
# 4. MediaAsset Model Tests
# ==============================================================================

def test_contentmanagement_mediaasset_number_generation(tenant_a):
    """Verify MediaAsset auto-generates sequential EMED- numbers."""
    m1 = _contentmanagement_media(tenant_a, title="Asset 1")
    m2 = _contentmanagement_media(tenant_a, title="Asset 2")
    assert m1.number.startswith("EMED-")
    assert m2.number.startswith("EMED-")
    assert m1.number != m2.number


def test_contentmanagement_mediaasset_str(tenant_a):
    """Verify MediaAsset __str__ includes number and title."""
    m = _contentmanagement_media(tenant_a, title="Homepage Hero")
    assert m.number in str(m)
    assert "Homepage Hero" in str(m)


def test_contentmanagement_mediaasset_optional_attributes(tenant_a, user_a):
    """Verify MediaAsset stores optional dimensions, caption, and uploaded_by."""
    m = _contentmanagement_media(
        tenant_a,
        title="Detailed Graphic",
        width_px=1920,
        height_px=1080,
        file_size_bytes=512000,
        caption="Full HD Visual",
        uploaded_by=user_a,
    )
    assert m.width_px == 1920
    assert m.height_px == 1080
    assert m.file_size_bytes == 512000
    assert m.caption == "Full HD Visual"
    assert m.uploaded_by == user_a


# ==============================================================================
# 5. ContentBlock Model Tests
# ==============================================================================

def test_contentmanagement_contentblock_number_generation(tenant_a):
    """Verify ContentBlock auto-generates sequential EBLK- numbers."""
    b1 = _contentmanagement_block(tenant_a, name="Block 1")
    b2 = _contentmanagement_block(tenant_a, name="Block 2")
    assert b1.number.startswith("EBLK-")
    assert b2.number.startswith("EBLK-")
    assert b1.number != b2.number


def test_contentmanagement_contentblock_str(tenant_a):
    """Verify ContentBlock __str__ includes number, name, and block type."""
    b = _contentmanagement_block(tenant_a, name="Navbar Promo Strip", block_type="cta_banner")
    assert b.number in str(b)
    assert "Navbar Promo Strip" in str(b)
    assert "Call to Action Strip" in str(b)


def test_contentmanagement_contentblock_catalog_relations(tenant_a, ecom_category_a, ecom_product_a, ecom_mediaasset_a):
    """Verify ContentBlock associates properly with MediaAsset, StoreCategory, and CatalogProduct."""
    b = _contentmanagement_block(
        tenant_a,
        name="Linked Hero Block",
        media_asset=ecom_mediaasset_a,
        target_category=ecom_category_a,
        target_product=ecom_product_a,
    )
    assert b.media_asset == ecom_mediaasset_a
    assert b.target_category == ecom_category_a
    assert b.target_product == ecom_product_a
