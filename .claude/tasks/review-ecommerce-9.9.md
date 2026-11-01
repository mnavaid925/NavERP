# Review Findings — Sub-module 9.9: Content Management System (CMS)

- **App:** `apps/ecommerce` (Module 9: eCommerce Management System)
- **Sub-module:** 9.9 Content Management System (CMS)
- **Review Range:** `42bddb89b161860bccfdf4fac370b60a2ff20366...HEAD`
- **Reviewers:** `code-reviewer`, `explorer`, `frontend-reviewer`, `performance-reviewer`, `qa-smoke-tester`, `security-reviewer`
- **Status:** Consolidated, deduplicated, and prioritized for Phase 5 `code-fixer`.

---

## Critical Findings (3)

### [C1] Missing `TenantUniqueMixin` on `ContentBlockForm` and `MediaAssetForm`
- **Files**:
  - `apps/ecommerce/forms/ContentManagement/ContentBlocks.py`
  - `apps/ecommerce/forms/ContentManagement/MediaAssets.py`
- **Problem**: Both forms inherit directly from `TenantModelForm` without `TenantUniqueMixin`. In NavERP, `TenantUniqueMixin` provides automatic assignment of `self.instance.tenant = self.tenant` on creation. Without it, forms may fail with `IntegrityError: Column 'tenant_id' cannot be null` or skip tenant number generation.
- **Fix**: Inherit `(TenantUniqueMixin, TenantModelForm)` on both form classes.
- **Status**: [x] fixed

### [C2] Cross-tenant user exposure & missing `author` validation in `BlogArticleForm`
- **File**: `apps/ecommerce/forms/ContentManagement/BlogArticles.py`
- **Problem**: `self.fields["author"].queryset` is set to `User.objects.filter(is_active=True).order_by("username")` without filtering by `tenant=self.tenant`. Also, `reject_foreign` only checks `["featured_media"]`, omitting `"author"`. A user can see and assign users from other workspaces.
- **Fix**: Filter `author` queryset by `tenant=self.tenant, is_active=True`, and add `"author"` to `reject_foreign(self, cleaned, ["featured_media", "author"])`.
- **Status**: [x] fixed

### [C3] Stored XSS vulnerability in CMS Page detail / preview via unsanitized `raw_html_body|safe`
- **Files**:
  - `templates/ecommerce/content_management/page/detail.html`
  - `apps/ecommerce/forms/ContentManagement/CmsPages.py`
- **Problem**: `page.raw_html_body|safe` renders unescaped HTML directly in the browser DOM. Unsanitized user HTML allows script injection or malicious iframes.
- **Fix**: Restrict raw script/event handler injection or sanitize HTML to safe tags/attributes, and verify only authenticated staff can submit content.
- **Status**: [x] fixed

---

## Important Findings (7)

### [I1] Silent blank rendering of target product name in Content Block templates (`target_product.title` vs `name`)
- **Files**:
  - `templates/ecommerce/content_management/block/list.html`
  - `templates/ecommerce/content_management/block/detail.html`
- **Problem**: Templates reference `{{ block_item.target_product.title }}` and `{{ content_block.target_product.title }}`. The `CatalogProduct` model field is `name`, not `title`. In Django templates, accessing a non-existent attribute evaluates to `""` silently (L8 contract drift), rendering blank labels.
- **Fix**: Change `.title` to `.name` in both templates.
- **Status**: [x] fixed

### [I2] `BlogArticle.published_at` is never populated upon publishing
- **Files**:
  - `apps/ecommerce/models/ContentManagement/BlogArticles.py`
  - `apps/ecommerce/forms/ContentManagement/BlogArticles.py`
- **Problem**: `published_at` is excluded from the form and not set on save. Articles published through the UI retain `published_at = None`.
- **Fix**: In `BlogArticle.save()`, auto-set `self.published_at = timezone.now()` when `self.status == "published"` and `self.published_at` is None.
- **Status**: [x] fixed

### [I3] Missing form `<label>` for `body_markdown` in Blog Article Form (Accessibility / WCAG 2.1)
- **File**: `templates/ecommerce/content_management/blog/form.html`
- **Problem**: Textarea `{{ form.body_markdown }}` lacks an associated `<label for="{{ form.body_markdown.id_for_label }}">` element.
- **Fix**: Add `<label for="{{ form.body_markdown.id_for_label }}" class="form-label">Article Body (Markdown) *</label>` inside the `form-group`.
- **Status**: [x] fixed

### [I4] Missing `select_related` on Foreign Keys in Detail Views causing lazy N+1 queries
- **Files**:
  - `apps/ecommerce/views/ContentManagement/BlogArticles.py`
  - `apps/ecommerce/views/ContentManagement/MediaAssets.py`
  - `apps/ecommerce/views/ContentManagement/ContentBlocks.py`
- **Problem**: Detail views call `ecommerce_object(...)` without `select_related`, triggering 1–3 extra SQL queries when rendering templates with FK attributes.
- **Fix**: Pass `select_related=("author", "featured_media")` for `BlogArticle`, `select_related=("uploaded_by",)` for `MediaAsset`, and `select_related=("media_asset", "target_product", "target_category")` for `ContentBlock`.
- **Status**: [x] fixed

### [I5] Heavy payload columns (`raw_html_body`, `content_json`, `body_markdown`) fetched in list views without `defer()`
- **Files**:
  - `apps/ecommerce/views/ContentManagement/CmsPages.py`
  - `apps/ecommerce/views/ContentManagement/BlogArticles.py`
- **Problem**: Full editorial text (potentially 50KB–200KB+) is retrieved for all 20 rows in list queries but not displayed in tables.
- **Fix**: Add `.defer("raw_html_body", "content_json")` to `CmsPage` list queryset and `.defer("body_markdown")` to `BlogArticle` list queryset.
- **Status**: [ ] open

### [I6] Reverse Tabnabbing risk on external `target="_blank"` anchors
- **Files**:
  - `templates/ecommerce/content_management/page/list.html`
  - `templates/ecommerce/content_management/page/detail.html`
  - `templates/ecommerce/content_management/media/list.html`
  - `templates/ecommerce/content_management/media/detail.html`
- **Problem**: External asset and preview links opening with `target="_blank"` omit `rel="noopener noreferrer"`.
- **Fix**: Add `rel="noopener noreferrer"` to all `<a ... target="_blank">` tags.
- **Status**: [ ] open

### [I7] Stored DOM XSS via unvalidated `cta_url` in ContentBlock
- **Files**:
  - `apps/ecommerce/forms/ContentManagement/ContentBlocks.py`
  - `templates/ecommerce/content_management/block/detail.html`
- **Problem**: `cta_url` is unvalidated and could accept `javascript:...` URIs rendered directly in `<a href="...">`.
- **Fix**: Add `clean_cta_url()` in `ContentBlockForm` requiring URLs to start with `/`, `#`, `http://`, or `https://`.
- **Status**: [ ] open

---

## Minor Findings (7)

### [M1] Superfluous JOIN on `featured_media` in `blogarticle_list`
- **File**: `apps/ecommerce/views/ContentManagement/BlogArticles.py`
- **Problem**: List view joins `featured_media` but template does not render it.
- **Fix**: Remove `"featured_media"` from `select_related` in `blogarticle_list`.
- **Status**: [ ] open

### [M2] Accessibility: Icon-only table action buttons lack explicit `aria-label` attributes
- **Files**:
  - `templates/ecommerce/content_management/page/list.html`
  - `templates/ecommerce/content_management/blog/list.html`
  - `templates/ecommerce/content_management/media/list.html`
  - `templates/ecommerce/content_management/block/list.html`
- **Problem**: Icon-only action links/buttons have `title` but lack `aria-label`.
- **Fix**: Add matching `aria-label` to each action button.
- **Status**: [ ] open

### [M3] `BlogArticleForm` does not lowercase or strip slug
- **File**: `apps/ecommerce/forms/ContentManagement/BlogArticles.py`
- **Problem**: Missing `clean_slug()` normalizing strings via `.strip().lower()`.
- **Fix**: Add `clean_slug()` method to normalize slug.
- **Status**: [ ] open

### [M4] Blog Article detail renders comma-separated tags as single monolithic badge
- **Files**:
  - `apps/ecommerce/models/ContentManagement/BlogArticles.py`
  - `templates/ecommerce/content_management/blog/detail.html`
- **Problem**: Multiple tags like `"news, updates"` appear in one badge.
- **Fix**: Add `tag_list` helper property on `BlogArticle` model and loop over chips in template.
- **Status**: [ ] open

### [M5] Seeder cross-tenant user fallback in `seed_ecommerce.py`
- **File**: `apps/ecommerce/management/commands/seed_ecommerce.py`
- **Problem**: Seeder uses `User.objects.filter(is_active=True).first()` without tenant filter.
- **Fix**: Scope by `User.objects.filter(tenant=tenant, is_active=True).first() or User.objects.filter(is_active=True).first()`.
- **Status**: [ ] open

### [M6] Table Name Defaulting on `CmsPage` (`ecommerce_cmspage` vs `ecommerce_cms_page`)
- **File**: `apps/ecommerce/models/ContentManagement/CmsPages.py`
- **Problem**: Contract specified `Table: ecommerce_cms_page`, but model defaulted to `ecommerce_cmspage`.
- **Fix**: Record in `.agents/tasks/gaps-ecommerce-9.9.md` to avoid disruption of migration 0026.
- **Status**: [ ] open

### [M7] Composite `(tenant, -created_at)` indexes omitted from CMS models
- **Files**:
  - `apps/ecommerce/models/ContentManagement/CmsPages.py`
  - `apps/ecommerce/models/ContentManagement/BlogArticles.py`
  - `apps/ecommerce/models/ContentManagement/MediaAssets.py`
  - `apps/ecommerce/models/ContentManagement/ContentBlocks.py`
- **Problem**: Default list pagination orders by `-created_at` without a composite index on `(tenant, -created_at)`.
- **Fix**: Record in `.agents/tasks/gaps-ecommerce-9.9.md`.
- **Status**: [ ] open
