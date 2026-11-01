# Contract — Sub-module 9.9: Content Management System (CMS) (Module 9: eCommerce Management System, `ecommerce`)

- **Sub-module:** 9.9 Content Management System (CMS) · **Module:** 9 eCommerce Management System · **App:** `apps/ecommerce`
- **Date:** 2026-11-01 · **Status:** FROZEN PRE-BUILD CONTRACT · **Phase:** 3.1 Spec
- **App Status:** Extending existing `apps/ecommerce/`. Next incremental migration: `0026_...`
- **Package Layout:** `ContentManagement/` across `models/`, `forms/`, `views/`, `urls/`, and templates `templates/ecommerce/content_management/`.

---

## 1. Models & CHOICES Contract

All top-level models inherit from `apps.ecommerce.models._base.TenantNumbered` (`tenant`, `number`, `created_at`, `updated_at`).

### 1.1 `CmsPage` (`apps/ecommerce/models/ContentManagement/CmsPages.py`)
- **Table:** `ecommerce_cms_page`
- **Number Prefix:** `EPAG` (`EPAG-00001`)
- **CHOICES:**
  - `PAGE_TYPE_CHOICES = [('standard', 'Standard Store Page'), ('landing', 'Promotional Landing Page'), ('policy', 'Store Policy / Legal'), ('about', 'About Us / Story'), ('contact', 'Contact Us'), ('homepage', 'Custom Homepage Layout')]`
  - `STATUS_CHOICES = [('draft', 'Draft'), ('scheduled', 'Scheduled'), ('published', 'Published'), ('archived', 'Archived')]`
  - `LAYOUT_CHOICES = [('full_width', 'Full Width (No Sidebars)'), ('boxed', 'Boxed Container'), ('sidebar_left', 'Left Sidebar'), ('sidebar_right', 'Right Sidebar'), ('minimal_landing', 'Minimal Landing (No Header/Footer)')]`
- **Fields:**
  - `tenant`: `ForeignKey('core.Tenant', on_delete=CASCADE, related_name='+')`
  - `number`: `CharField(max_length=20, editable=False)`
  - `title`: `CharField(max_length=255, help_text="Public page headline")`
  - `slug`: `SlugField(max_length=255, help_text="URL path slug")`
  - `page_type`: `CharField(max_length=25, choices=PAGE_TYPE_CHOICES, default='standard')`
  - `status`: `CharField(max_length=20, choices=STATUS_CHOICES, default='draft')`
  - `template_layout`: `CharField(max_length=25, choices=LAYOUT_CHOICES, default='full_width')`
  - `meta_title`: `CharField(max_length=255, blank=True, help_text="SEO title tag")`
  - `meta_description`: `TextField(max_length=500, blank=True, help_text="SEO meta description snippet")`
  - `canonical_url`: `URLField(max_length=500, blank=True, help_text="Canonical URL override")`
  - `is_indexable`: `BooleanField(default=True, help_text="Allow search engines to index")`
  - `content_json`: `JSONField(default=dict, blank=True, help_text="Structured layout blocks payload")`
  - `raw_html_body`: `TextField(blank=True, help_text="Editorial or fallback HTML content")`
  - `published_at`: `DateTimeField(null=True, blank=True)`
  - `view_count`: `PositiveIntegerField(default=0)`
  - `is_ab_test_active`: `BooleanField(default=False)`
  - `ab_variant_label`: `CharField(max_length=50, blank=True, help_text="A/B variant name e.g. Variant B")`
  - `ab_traffic_percentage`: `PositiveSmallIntegerField(default=50, validators=[MinValueValidator(0), MaxValueValidator(100)])`
  - `created_at`: `DateTimeField(auto_now_add=True)`
  - `updated_at`: `DateTimeField(auto_now=True)`
- **Constraints & Indexes:**
  - `UniqueConstraint(fields=['tenant', 'number'], name='ecommerce_epag_tenant_num_uniq')`
  - `UniqueConstraint(fields=['tenant', 'slug'], name='ecommerce_epag_tenant_slug_uniq')`
  - `Index(fields=['tenant', 'status', 'page_type'], name='idx_epag_ten_stat_type')`
  - `Index(fields=['tenant', 'is_ab_test_active'], name='idx_epag_ten_ab')`

---

### 1.2 `BlogArticle` (`apps/ecommerce/models/ContentManagement/BlogArticles.py`)
- **Table:** `ecommerce_blog_article`
- **Number Prefix:** `EBLG` (`EBLG-00001`)
- **CHOICES:**
  - `CATEGORY_CHOICES = [('news', 'Company News'), ('product_spotlight', 'Product Spotlight'), ('guides_tutorials', 'Guides & Tutorials'), ('lifestyle', 'Lifestyle & Trends'), ('company_updates', 'Announcements')]`
  - `STATUS_CHOICES = [('draft', 'Draft'), ('scheduled', 'Scheduled'), ('published', 'Published'), ('archived', 'Archived')]`
- **Fields:**
  - `tenant`: `ForeignKey('core.Tenant', on_delete=CASCADE, related_name='+')`
  - `number`: `CharField(max_length=20, editable=False)`
  - `title`: `CharField(max_length=255, help_text="Article title")`
  - `slug`: `SlugField(max_length=255, help_text="URL slug")`
  - `author`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=SET_NULL, null=True, blank=True, related_name='ecommerce_blog_articles')`
  - `category`: `CharField(max_length=30, choices=CATEGORY_CHOICES, default='guides_tutorials')`
  - `excerpt`: `TextField(max_length=500, help_text="Summary for cards and SEO")`
  - `body_markdown`: `TextField(help_text="Detailed article markdown text")`
  - `featured_media`: `ForeignKey('ecommerce.MediaAsset', on_delete=SET_NULL, null=True, blank=True, related_name='blog_articles')`
  - `status`: `CharField(max_length=20, choices=STATUS_CHOICES, default='draft')`
  - `tags`: `CharField(max_length=255, blank=True, help_text="Comma-separated keyword tags")`
  - `reading_time_minutes`: `PositiveSmallIntegerField(default=3, help_text="Estimated read time in minutes")`
  - `allow_comments`: `BooleanField(default=True)`
  - `is_featured`: `BooleanField(default=False)`
  - `published_at`: `DateTimeField(null=True, blank=True)`
  - `view_count`: `PositiveIntegerField(default=0)`
  - `created_at`: `DateTimeField(auto_now_add=True)`
  - `updated_at`: `DateTimeField(auto_now=True)`
- **Constraints & Indexes:**
  - `UniqueConstraint(fields=['tenant', 'number'], name='ecommerce_eblg_tenant_num_uniq')`
  - `UniqueConstraint(fields=['tenant', 'slug'], name='ecommerce_eblg_tenant_slug_uniq')`
  - `Index(fields=['tenant', 'status', 'category'], name='idx_eblg_ten_stat_cat')`
  - `Index(fields=['tenant', 'is_featured'], name='idx_eblg_ten_feat')`

---

### 1.3 `MediaAsset` (`apps/ecommerce/models/ContentManagement/MediaAssets.py`)
- **Table:** `ecommerce_media_asset`
- **Number Prefix:** `EMED` (`EMED-00001`)
- **CHOICES:**
  - `MEDIA_TYPE_CHOICES = [('image', 'Image / Graphic'), ('video', 'Video Embed / Clip'), ('document', 'PDF Document'), ('banner', 'Promotional Banner'), ('icon', 'SVG / Icon')]`
  - `FOLDER_CHOICES = [('banners', 'Store Banners'), ('blog', 'Blog Imagery'), ('pages', 'Page Assets'), ('marketing', 'Marketing Collateral'), ('icons', 'UI Icons'), ('uncategorized', 'Uncategorized')]`
- **Fields:**
  - `tenant`: `ForeignKey('core.Tenant', on_delete=CASCADE, related_name='+')`
  - `number`: `CharField(max_length=20, editable=False)`
  - `title`: `CharField(max_length=255, help_text="Media asset display name")`
  - `file_url`: `URLField(max_length=500, help_text="Direct HTTPS asset URL")`
  - `alt_text`: `CharField(max_length=255, blank=True, help_text="Accessibility & SEO alt text")`
  - `caption`: `CharField(max_length=255, blank=True, help_text="Optional asset caption")`
  - `media_type`: `CharField(max_length=20, choices=MEDIA_TYPE_CHOICES, default='image')`
  - `folder_category`: `CharField(max_length=30, choices=FOLDER_CHOICES, default='uncategorized')`
  - `file_size_bytes`: `PositiveIntegerField(default=0, help_text="File size in bytes")`
  - `mime_type`: `CharField(max_length=100, default='image/jpeg')`
  - `width_px`: `PositiveIntegerField(null=True, blank=True)`
  - `height_px`: `PositiveIntegerField(null=True, blank=True)`
  - `uploaded_by`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=SET_NULL, null=True, blank=True, related_name='uploaded_ecommerce_media')`
  - `created_at`: `DateTimeField(auto_now_add=True)`
  - `updated_at`: `DateTimeField(auto_now=True)`
- **Constraints & Indexes:**
  - `UniqueConstraint(fields=['tenant', 'number'], name='ecommerce_emed_tenant_num_uniq')`
  - `Index(fields=['tenant', 'media_type', 'folder_category'], name='idx_emed_ten_type_cat')`

---

### 1.4 `ContentBlock` (`apps/ecommerce/models/ContentManagement/ContentBlocks.py`)
- **Table:** `ecommerce_content_block`
- **Number Prefix:** `EBLK` (`EBLK-00001`)
- **CHOICES:**
  - `BLOCK_TYPE_CHOICES = [('hero_banner', 'Hero Banner with CTA'), ('feature_grid', '3-Column Feature Grid'), ('product_carousel', 'Catalog Product Carousel'), ('testimonial', 'Customer Testimonial Slider'), ('cta_banner', 'Call to Action Strip'), ('rich_text', 'Formatted Editorial Text'), ('faq_accordion', 'FAQ Accordion'), ('newsletter_signup', 'Newsletter Signup Strip')]`
- **Fields:**
  - `tenant`: `ForeignKey('core.Tenant', on_delete=CASCADE, related_name='+')`
  - `number`: `CharField(max_length=20, editable=False)`
  - `name`: `CharField(max_length=255, help_text="Internal block identifier")`
  - `block_type`: `CharField(max_length=30, choices=BLOCK_TYPE_CHOICES, default='hero_banner')`
  - `headline`: `CharField(max_length=255, blank=True, help_text="Promotional heading")`
  - `subheadline`: `CharField(max_length=255, blank=True, help_text="Secondary sub-title")`
  - `body_text`: `TextField(blank=True, help_text="Descriptive body content")`
  - `media_asset`: `ForeignKey('ecommerce.MediaAsset', on_delete=SET_NULL, null=True, blank=True, related_name='content_blocks')`
  - `cta_label`: `CharField(max_length=100, blank=True, help_text="Button text")`
  - `cta_url`: `CharField(max_length=255, blank=True, help_text="Target button link")`
  - `target_category`: `ForeignKey('ecommerce.StoreCategory', on_delete=SET_NULL, null=True, blank=True, related_name='content_blocks')`
  - `target_product`: `ForeignKey('ecommerce.CatalogProduct', on_delete=SET_NULL, null=True, blank=True, related_name='content_blocks')`
  - `bg_color_class`: `CharField(max_length=50, default='bg-slate-50', help_text="Tailwind background class")`
  - `text_color_class`: `CharField(max_length=50, default='text-slate-900', help_text="Tailwind text class")`
  - `sort_order`: `PositiveIntegerField(default=0, help_text="Display priority order")`
  - `is_active`: `BooleanField(default=True)`
  - `created_at`: `DateTimeField(auto_now_add=True)`
  - `updated_at`: `DateTimeField(auto_now=True)`
- **Constraints & Indexes:**
  - `UniqueConstraint(fields=['tenant', 'number'], name='ecommerce_eblk_tenant_num_uniq')`
  - `Index(fields=['tenant', 'block_type', 'is_active'], name='idx_eblk_ten_type_act')`
  - `Index(fields=['tenant', 'sort_order'], name='idx_eblk_ten_order')`

---

## 2. Forms Contract

All forms inherit from `apps.core.forms.TenantModelForm` and enforce tenant scoping in `__init__`.

### 2.1 `CmsPageForm` (`apps/ecommerce/forms/ContentManagement/CmsPages.py`)
- **Model:** `CmsPage`
- **Fields:** `['title', 'slug', 'page_type', 'status', 'template_layout', 'meta_title', 'meta_description', 'canonical_url', 'is_indexable', 'raw_html_body', 'is_ab_test_active', 'ab_variant_label', 'ab_traffic_percentage']`
- **Excludes:** `['tenant', 'number', 'view_count', 'published_at', 'content_json', 'created_at', 'updated_at']`
- **Tenant Validation:** Automatic slug uniqueness check scoped to `request.tenant`.

### 2.2 `BlogArticleForm` (`apps/ecommerce/forms/ContentManagement/BlogArticles.py`)
- **Model:** `BlogArticle`
- **Fields:** `['title', 'slug', 'author', 'category', 'excerpt', 'body_markdown', 'featured_media', 'status', 'tags', 'reading_time_minutes', 'allow_comments', 'is_featured']`
- **Excludes:** `['tenant', 'number', 'view_count', 'published_at', 'created_at', 'updated_at']`
- **Tenant Scoping:** `author` queryset filtered to `User.objects.filter(tenants=self.tenant)` or active workspace users. `featured_media` queryset filtered to `MediaAsset.objects.filter(tenant=self.tenant)`.

### 2.3 `MediaAssetForm` (`apps/ecommerce/forms/ContentManagement/MediaAssets.py`)
- **Model:** `MediaAsset`
- **Fields:** `['title', 'file_url', 'alt_text', 'caption', 'media_type', 'folder_category', 'file_size_bytes', 'mime_type', 'width_px', 'height_px']`
- **Excludes:** `['tenant', 'number', 'uploaded_by', 'created_at', 'updated_at']`
- **Validation:** Enforces `file_url` starts with `http://` or `https://`.

### 2.4 `ContentBlockForm` (`apps/ecommerce/forms/ContentManagement/ContentBlocks.py`)
- **Model:** `ContentBlock`
- **Fields:** `['name', 'block_type', 'headline', 'subheadline', 'body_text', 'media_asset', 'cta_label', 'cta_url', 'target_category', 'target_product', 'bg_color_class', 'text_color_class', 'sort_order', 'is_active']`
- **Excludes:** `['tenant', 'number', 'created_at', 'updated_at']`
- **Tenant Scoping:** `media_asset`, `target_category`, and `target_product` querysets all strictly filtered to `self.tenant`.

---

## 3. URLs & Routes Contract (`app_name = "ecommerce"`)

| URL Pattern | View Name | Route Name | Perms |
|---|---|---|---|
| `cms/pages/` | `cmspage_list` | `ecommerce:cmspage_list` | Login required |
| `cms/pages/create/` | `cmspage_create` | `ecommerce:cmspage_create` | Login required |
| `cms/pages/<int:pk>/` | `cmspage_detail` | `ecommerce:cmspage_detail` | Login required |
| `cms/pages/<int:pk>/edit/` | `cmspage_edit` | `ecommerce:cmspage_edit` | Login required |
| `cms/pages/<int:pk>/delete/` | `cmspage_delete` | `ecommerce:cmspage_delete` | POST + Tenant Admin |
| `cms/pages/<int:pk>/preview/` | `cmspage_preview` | `ecommerce:cmspage_preview` | Login required |
| `cms/blog/` | `blogarticle_list` | `ecommerce:blogarticle_list` | Login required |
| `cms/blog/create/` | `blogarticle_create` | `ecommerce:blogarticle_create` | Login required |
| `cms/blog/<int:pk>/` | `blogarticle_detail` | `ecommerce:blogarticle_detail` | Login required |
| `cms/blog/<int:pk>/edit/` | `blogarticle_edit` | `ecommerce:blogarticle_edit` | Login required |
| `cms/blog/<int:pk>/delete/` | `blogarticle_delete` | `ecommerce:blogarticle_delete` | POST + Tenant Admin |
| `cms/media/` | `mediaasset_list` | `ecommerce:mediaasset_list` | Login required |
| `cms/media/create/` | `mediaasset_create` | `ecommerce:mediaasset_create` | Login required |
| `cms/media/<int:pk>/` | `mediaasset_detail` | `ecommerce:mediaasset_detail` | Login required |
| `cms/media/<int:pk>/edit/` | `mediaasset_edit` | `ecommerce:mediaasset_edit` | Login required |
| `cms/media/<int:pk>/delete/` | `mediaasset_delete` | `ecommerce:mediaasset_delete` | POST + Tenant Admin |
| `cms/blocks/` | `contentblock_list` | `ecommerce:contentblock_list` | Login required |
| `cms/blocks/create/` | `contentblock_create` | `ecommerce:contentblock_create` | Login required |
| `cms/blocks/<int:pk>/` | `contentblock_detail` | `ecommerce:contentblock_detail` | Login required |
| `cms/blocks/<int:pk>/edit/` | `contentblock_edit` | `ecommerce:contentblock_edit` | Login required |
| `cms/blocks/<int:pk>/delete/` | `contentblock_delete` | `ecommerce:contentblock_delete` | POST + Tenant Admin |

---

## 4. View Context Keys Contract (L7 / L8)

### 4.1 `cmspage_list`
- `pages`: Paginator page object
- `page_type_choices`: `CmsPage.PAGE_TYPE_CHOICES`
- `status_choices`: `CmsPage.STATUS_CHOICES`
- `layout_choices`: `CmsPage.LAYOUT_CHOICES`
- `selected_type`: string
- `selected_status`: string
- `selected_layout`: string
- `search_query`: string

### 4.2 `cmspage_detail`
- `page`: `CmsPage` instance

### 4.3 `cmspage_create` & `cmspage_edit`
- `form`: `CmsPageForm`
- `page`: `CmsPage` instance or `None`

### 4.4 `blogarticle_list`
- `articles`: Paginator page object
- `category_choices`: `BlogArticle.CATEGORY_CHOICES`
- `status_choices`: `BlogArticle.STATUS_CHOICES`
- `selected_category`: string
- `selected_status`: string
- `search_query`: string

### 4.5 `blogarticle_detail`
- `article`: `BlogArticle` instance

### 4.6 `blogarticle_create` & `blogarticle_edit`
- `form`: `BlogArticleForm`
- `article`: `BlogArticle` instance or `None`

### 4.7 `mediaasset_list`
- `assets`: Paginator page object
- `media_type_choices`: `MediaAsset.MEDIA_TYPE_CHOICES`
- `folder_choices`: `MediaAsset.FOLDER_CHOICES`
- `selected_type`: string
- `selected_folder`: string
- `search_query`: string

### 4.8 `mediaasset_detail`
- `asset`: `MediaAsset` instance

### 4.9 `mediaasset_create` & `mediaasset_edit`
- `form`: `MediaAssetForm`
- `asset`: `MediaAsset` instance or `None`

### 4.10 `contentblock_list`
- `blocks`: Paginator page object
- `block_type_choices`: `ContentBlock.BLOCK_TYPE_CHOICES`
- `selected_type`: string
- `selected_active`: string
- `search_query`: string

### 4.11 `contentblock_detail`
- `block`: `ContentBlock` instance

### 4.12 `contentblock_create` & `contentblock_edit`
- `form`: `ContentBlockForm`
- `block`: `ContentBlock` instance or `None`
