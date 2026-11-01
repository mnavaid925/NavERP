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

---

## Reviewer 2: `explorer`

### Critical Findings
*None.*

### Important Findings
- **[IR2-01] Silent Blank Product Name Rendering in Content Block Templates (Duplicate of IR1-01)**
  - **Files**:
    - `templates/ecommerce/content_management/block/list.html`
    - `templates/ecommerce/content_management/block/detail.html`
  - **Problem**: Both templates reference `target_product.title`. `CatalogProduct` has `name`, not `title`.
  - **Fix**: Change `target_product.title` to `target_product.name`.

- **[IR2-02] Context Variable Discrepancy for Content Block Templates (`block` vs `content_block`)**
  - **Files**:
    - `templates/ecommerce/content_management/block/detail.html`
    - `templates/ecommerce/content_management/block/form.html`
    - `apps/ecommerce/views/ContentManagement/ContentBlocks.py`
  - **Problem**: Contract lists `block`, but Django template keyword `{% block ... %}` shadows `block` variable. View passes both `block` and `content_block`.
  - **Fix**: Keep both `block` and `content_block` in view context for backward compatibility and document in gap register.

### Minor Findings
- **[MR2-01] Table Name Defaulting on `CmsPage` (`ecommerce_cmspage` vs `ecommerce_cms_page`) (Duplicate of MR1-01)**
  - **File**: `apps/ecommerce/models/ContentManagement/CmsPages.py`
  - **Fix**: Document in gap register.

- **[MR2-02] Missing Foreign Key Eager-Loading in Detail Views (N+1 Query Avoidance) (Duplicate of MR1-02)**
  - **Files**:
    - `apps/ecommerce/views/ContentManagement/BlogArticles.py`
    - `apps/ecommerce/views/ContentManagement/MediaAssets.py`
    - `apps/ecommerce/views/ContentManagement/ContentBlocks.py`
  - **Fix**: Pass `select_related` on FKs in detail views.

---

## Reviewer 3: `frontend-reviewer`

### Critical Findings
*None.*

### Important Findings
- **[IFR-01] Silent blank rendering of target product name in Content Block templates (Duplicate of IR1-01 / IR2-01)**
  - **Files**:
    - `templates/ecommerce/content_management/block/list.html`
    - `templates/ecommerce/content_management/block/detail.html`
  - **Problem**: Both templates reference `target_product.title` instead of `target_product.name`.
  - **Fix**: Replace `.title` with `.name`.

- **[IFR-02] Accessibility: Missing form `<label>` for `body_markdown` in Blog Article Form**
  - **File**: `templates/ecommerce/content_management/blog/form.html`
  - **Problem**: Textarea `{{ form.body_markdown }}` lacks an associated `<label for="...">`.
  - **Fix**: Add `<label for="{{ form.body_markdown.id_for_label }}" class="form-label">Article Body (Markdown) *</label>`.

- **[IFR-03] Reverse tabnabbing risk: Missing `rel="noopener noreferrer"` on `target="_blank"` links**
  - **Files**:
    - `templates/ecommerce/content_management/media/list.html`
    - `templates/ecommerce/content_management/media/detail.html`
    - `templates/ecommerce/content_management/page/list.html`
    - `templates/ecommerce/content_management/page/detail.html`
  - **Problem**: Links opening with `target="_blank"` omit `rel="noopener noreferrer"`.
  - **Fix**: Add `rel="noopener noreferrer"` to all `<a ... target="_blank">` tags.

### Minor Findings
- **[MFR-01] Accessibility: Icon-only table action buttons lack explicit `aria-label` attributes**
  - **Files**: All 4 list templates (`page/list.html`, `blog/list.html`, `media/list.html`, `block/list.html`)
  - **Fix**: Add `aria-label` matching `title` on icon-only action links/buttons.

- **[MFR-02] Blog Article detail renders comma-separated tags as a single monolithic badge**
  - **File**: `templates/ecommerce/content_management/blog/detail.html`
  - **Fix**: Add `tag_list` helper property on `BlogArticle` model or split in template to render individual badge chips.

- **[MFR-03] CTA URL in Content Block Detail component simulator lacks protocol safeguard**
  - **File**: `templates/ecommerce/content_management/block/detail.html`
  - **Fix**: Restrict or validate protocol on CTA preview button.

---

## Reviewer 4: `performance-reviewer`

### Critical Findings
*None.*

### Important Findings
- **[IPR-01] Missing `select_related` on Foreign Keys in Detail Views (Duplicate of MR1-02 / MR2-02)**
  - **Files**:
    - `apps/ecommerce/views/ContentManagement/BlogArticles.py` (`blogarticle_detail`)
    - `apps/ecommerce/views/ContentManagement/MediaAssets.py` (`mediaasset_detail`)
    - `apps/ecommerce/views/ContentManagement/ContentBlocks.py` (`contentblock_detail`)
  - **Problem**: Detail templates reference FK attributes (`featured_media`, `author`, `uploaded_by`, `media_asset`, `target_category`, `target_product`) resulting in 1–3 additional lazy queries per page load.
  - **Fix**: Supply `select_related` in `ecommerce_object(...)` calls.

- **[IPR-02] Heavy payload columns (`raw_html_body`, `content_json`, `body_markdown`) fetched in list views without `defer()`**
  - **Files**:
    - `apps/ecommerce/views/ContentManagement/CmsPages.py` (`cmspage_list`)
    - `apps/ecommerce/views/ContentManagement/BlogArticles.py` (`blogarticle_list`)
  - **Problem**: Full text bodies (potentially 50KB–200KB+) are retrieved for all 20 rows in list views, none of which are rendered in table columns.
  - **Fix**: Add `.defer("raw_html_body", "content_json")` to `CmsPage` queryset and `.defer("body_markdown")` to `BlogArticle` queryset.

- **[IPR-03] Missing `(tenant, -created_at)` and composite sort order indexes on CMS models**
  - **Files**:
    - `apps/ecommerce/models/ContentManagement/CmsPages.py`
    - `apps/ecommerce/models/ContentManagement/BlogArticles.py`
    - `apps/ecommerce/models/ContentManagement/MediaAssets.py`
    - `apps/ecommerce/models/ContentManagement/ContentBlocks.py`
  - **Problem**: Default list queries order by `["-created_at"]` under `tenant_id = ?`, triggering a filesort without a composite index on `(tenant, -created_at)`.
  - **Fix**: Add composite indexes in next migration or record in gap register.

### Minor Findings
- **[MPR-01] Superfluous JOIN on `featured_media` in `blogarticle_list`**
  - **File**: `apps/ecommerce/views/ContentManagement/BlogArticles.py`
  - **Problem**: List view joins `featured_media` but template does not render it.
  - **Fix**: Remove `"featured_media"` from `select_related` in `blogarticle_list`.

- **[MPR-02] Unbounded global User queryset in `BlogArticleForm.__init__` (Duplicate of CR1-01)**
  - **File**: `apps/ecommerce/forms/ContentManagement/BlogArticles.py`
  - **Fix**: Filter by `tenant=self.tenant`.



