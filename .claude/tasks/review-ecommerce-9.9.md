# Code Review Findings — Sub-module 9.9: Content Management System (CMS)

**Review Range**: `42bddb89b161860bccfdf4fac370b60a2ff20366...HEAD`  
**Target App**: `apps/ecommerce/` & `apps/core/navigation.py`  
**Module**: 9 eCommerce Management System (`ecommerce`)

---

## Reviewer 1: `code-reviewer`

### Critical Findings
- **[CR1-01] Cross-tenant user exposure & missing IDOR validation for `author` in `BlogArticleForm`**
  - **File**: `apps/ecommerce/forms/ContentManagement/BlogArticles.py`
  - **Problem**: In `BlogArticleForm.__init__`, `self.fields["author"].queryset` is set to `User.objects.filter(is_active=True).order_by("username")` without filtering by `tenant=self.tenant`. In `clean()`, `reject_foreign` only checks `["featured_media"]`, omitting `"author"`.
  - **Fix**: Filter `author` queryset by `tenant=self.tenant` and add `"author"` to `reject_foreign`.

### Important Findings
- **[IR1-01] Silent blank rendering of target product name in content block templates (Contract drift / L8)**
  - **Files**:
    - `templates/ecommerce/content_management/block/list.html`
    - `templates/ecommerce/content_management/block/detail.html`
  - **Problem**: Both templates reference `target_product.title`. `CatalogProduct` field is `name`, not `title`. Evaluates to empty string silently.
  - **Fix**: Replace `.title` with `.name` in both templates.

- **[IR1-02] `BlogArticle.published_at` is never populated upon publishing**
  - **Files**:
    - `apps/ecommerce/models/ContentManagement/BlogArticles.py`
    - `apps/ecommerce/forms/ContentManagement/BlogArticles.py`
  - **Problem**: `published_at` is excluded from form and not assigned on save. Published articles retain `published_at = None`.
  - **Fix**: Auto-populate `self.published_at = timezone.now()` in `BlogArticle.save()` when `status == "published"` and `published_at` is unset.

- **[IR1-03] Unsanitized `raw_html_body` rendered with `|safe` in CMS Page detail view**
  - **File**: `templates/ecommerce/content_management/page/detail.html`
  - **Problem**: `{{ page.raw_html_body|safe }}` renders unescaped HTML.
  - **Fix**: Ensure CMS page edit/create requires `@tenant_admin_required` or document trust boundary.

### Minor Findings
- **[MR1-01] `CmsPage` omitted `db_table = "ecommerce_cms_page"` in model `Meta`**
  - **File**: `apps/ecommerce/models/ContentManagement/CmsPages.py`
  - **Problem**: Defaults to `ecommerce_cmspage`. Document in gap register.

- **[MR1-02] Missing `select_related` in detail views causing N+1 queries**
  - **Files**:
    - `apps/ecommerce/views/ContentManagement/BlogArticles.py` (`blogarticle_detail`)
    - `apps/ecommerce/views/ContentManagement/MediaAssets.py` (`mediaasset_detail`)
    - `apps/ecommerce/views/ContentManagement/ContentBlocks.py` (`contentblock_detail`)
  - **Fix**: Pass `select_related` to `ecommerce_object(...)`.

- **[MR1-03] `BlogArticleForm` does not lowercase or strip slug**
  - **File**: `apps/ecommerce/forms/ContentManagement/BlogArticles.py`
  - **Fix**: Add `clean_slug()` normalizing `.strip().lower()`.
