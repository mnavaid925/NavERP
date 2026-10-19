# Phase 4 Review Findings — Sales 8.11 Customer Success & Account Management

**Base Commit**: `db0cfe4b34538b933a169b722181f11c614f4a9c`
**Head Commit**: `7cd8e4591bf1da1519fd2f86a6b07987eb0b6718`
**Reviewed By**: 6 serial reviewers (`code-reviewer` → `explorer` → `frontend-reviewer` → `performance-reviewer` → `qa-smoke-tester` → `security-reviewer`)

---

## 1. Code Reviewer (`code-reviewer`)

### Critical
- **CR-C1**: `apps/sales/views/CustomerSuccess/CustomerHealthScores.py:113, 141, 169` (and across all 12 call sites in `CustomerRenewals.py:122, 151, 178`, `CustomerOnboardings.py:124, 152, 180`, `CustomerBusinessReviews.py:127, 155, 183`) — `write_audit_log` signature mismatch: arguments are passed as `write_audit_log(request.user, "CREATE", obj, ...)` instead of `write_audit_log(user, obj, action, changes=None, tenant=None)`. Because the second argument `obj` receives a string literal, `write_audit_log` executes `ContentType.objects.get_for_model(obj.__class__)`, which crashes every create, edit, and delete view with `AttributeError: type object 'str' has no attribute '_meta'` (HTTP 500). Fix: swap parameters to `write_audit_log(request.user, obj, "create", message, tenant=request.tenant)` (and in delete views, call `write_audit_log` before calling `obj.delete()`).

### Important
- **CR-I1**: `templates/sales/customersuccess/customerrenewal/detail.html:133` and `templates/sales/customersuccess/customeronboarding/detail.html:135` — `SalesOrder` field mismatch: templates reference `{{ obj.original_order.order_number }}` and `{{ obj.sales_order.order_number }}`. `scm.SalesOrder` inherits from `TenantNumbered` where the document identifier is `number` (`SO-00001`), not `order_number`. The linked sales order renders silently blank. Fix: replace `.order_number` with `.number`.
- **CR-I2**: `templates/sales/customersuccess/customerhealthscore/detail.html:76, 78` — Broken template filter arithmetic: `{{ obj.overall_score|add:"-"|add:obj.previous_score }}` fails because Django's `add` filter cannot subtract with string `"-"`, silently evaluating to an empty string and rendering `(+ )` or `(- )`. Fix: define a `@property` `score_delta` on `CustomerHealthScore` (returning `self.overall_score - self.previous_score if self.previous_score is not None else None`) and render `{{ obj.score_delta }}` in the template.
- **CR-I3**: `templates/sales/customersuccess/customerhealthscore/list.html:199`, `detail.html:35` (and across renewal, onboarding, and review list/detail templates) — Delete buttons are visible to non-admin users, but all delete views enforce `@tenant_admin_required`. Clicking the button returns a 403 Forbidden error for standard users. Fix: wrap delete forms/buttons with `{% if request.user.is_superuser or request.user.is_tenant_admin %}`.

### Minor
- **CR-M1**: `templates/sales/customersuccess/customerrenewal/list.html:76-115`, `customeronboarding/list.html:74-114`, `customerbusinessreview/list.html:74-115` — List filter completeness: views pass `owners` / `csm_users` (and parse `owner`/`lead_csm` with `.isdigit()`), and pass `playbook_choices` / `template_choices`, but the list templates omit filter dropdowns for owner/CSM and playbooks/templates. Fix: add the corresponding `<select>` elements to the list filter bars.
- **CR-M2**: `apps/sales/forms/CustomerSuccess/CustomerOnboardings.py:26, 44` — Overwritten form field: `time_to_value_days` is an editable input on `CustomerOnboardingForm`, but `CustomerOnboarding.save()` automatically overwrites `self.time_to_value_days` whenever `actual_go_live_date` and `kickoff_date` are present. Fix: exclude `time_to_value_days` from `Meta.fields` and display it as read-only computed telemetry.

### Strengths Noted
- Core-Spine Reuse: Reuses `core.Party`, `crm.Opportunity`, `scm.SalesOrder`, `sales.AccountPlan`, `accounting.Currency`, and `accounts.User`. Zero duplicate tables.
- Multi-Tenant Isolation: All models extend `TenantNumbered` with `(tenant, number)` uniqueness constraints. Form FKs are filtered to `request.tenant` via `TenantModelForm`.
- Clean 1:1 package layout across models, forms, views, and urls.

---

## 2. Explorer (`explorer`)

### Critical
- *None.*

### Important
- **EX-I1**: `templates/sales/customersuccess/customerrenewal/detail.html:133` and `templates/sales/customersuccess/customeronboarding/detail.html:135` — Inexistent `order_number` attribute accessed on `scm.SalesOrder`: `scm.SalesOrder` inherits from `TenantNumbered` with document identifier `number` (`SO-00001`), not `order_number`. In templates, `{{ obj.original_order.order_number }}` and `{{ obj.sales_order.order_number }}` evaluate to empty string, leaving sales order links blank. Fix: replace with `.number`. (Duplicates CR-I1).

### Minor
- **EX-M1**: `apps/sales/views/CustomerSuccess/CustomerHealthScores.py:204` — Context key drift in `customer_health_console`: passes `"all_scores": all_scores[:25]` instead of `"health_scores": all_scores[:25]` pinned in contract section 3.1. Fix: pass `"health_scores": all_scores[:25]`.
- **EX-M2**: `apps/sales/views/CustomerSuccess/CustomerOnboardings.py:208` — Context key omission in `customer_onboarding_hub`: passes `avg_ttv` only nested inside `stats["avg_ttv"]`. Contract pins top-level key `avg_ttv`. Fix: pass `"avg_ttv": stats.get("avg_ttv")` in context dictionary.

### Strengths Noted
- Exact contract conformity: All 4 models, choice tuples, unique constraints, and 12 indexes (< 28 chars) match contract.
- Re-exports in models, forms, views, and urls are complete.
- All 25 URLs correctly hooked, and `LIVE_LINKS["8.11"]` maps exact NavERP.md bullets.
- L33 badge palette compliance: strictly color-named classes (`badge-green`, `badge-amber`, `badge-red`, `badge-info`, `badge-slate`).

---

## 3. Frontend Reviewer (`frontend-reviewer`)

### Critical
- *None.*

### Important
- **FE-I1**: `templates/sales/customersuccess/customerhealthscore/detail.html:76, 78` — Invalid Django Filter Chaining for Math Subtraction: `{{ obj.overall_score|add:"-"|add:obj.previous_score }}` fails because Django's `add` filter cannot subtract with string `"-"`, silently evaluating to an empty string and rendering `(+)` and `()`. Fix: define `@property def score_delta(self)` on `CustomerHealthScore` model and render `{{ obj.score_delta }}` in the template. (Duplicates CR-I2).
- **FE-I2**: `templates/sales/customersuccess/customerhealthscore/list.html:234, 244` and `customerbusinessreview/list.html:234, 244` — Active Filter Query Params Dropped Across Pagination Links: `customerhealthscore/list.html` omits `is_churn_risk` in page 2+ links; `customerbusinessreview/list.html` omits `template_type` and `is_referenceable` in pagination links. Fix: append `{% if active_filters.is_churn_risk %}&is_churn_risk={{ active_filters.is_churn_risk }}{% endif %}` and corresponding params to pagination links.

### Minor
- **FE-M1**: `customerhealthscore/list.html`, `customeronboarding/list.html`, `customerrenewal/list.html`, `customerbusinessreview/list.html` — Missing Accessible Names on List Filter Form Inputs & Selects: search inputs and filter selects lack `aria-label` attributes. Fix: add `aria-label="Search records"` and `aria-label="Filter by ..."` to inputs and selects.
- **FE-M2**: `onboarding_hub.html:119, 172`, `qbr_studio.html:134`, `advocacy_hub.html:104, 150` — Defensive None-Safe Formatting on Lead CSM Lookups in Consoles: lines render `{{ rev.lead_csm.get_full_name|default:rev.lead_csm.username }}` without wrapping in `{% if rev.lead_csm %}...{% else %}—{% endif %}` (Lesson L10). Fix: wrap in `{% if rev.lead_csm %}`.
- **FE-M3**: Directional Utility Classes in Place of Logical RTL Properties: replace physical `border-l-*`, `pl-*`, and `ml-*` with logical Tailwind CSS classes `border-s-*`, `ps-*`, and `ms-*`.

### Strengths Noted
- Zero comment leaks (L2) across all 17 templates.
- 100% compliant color-named badges (`badge-green`, `badge-red`, `badge-amber`, `badge-info`, `badge-muted`, `badge-slate`) and stat icons (`blue`, `green`, `orange`, `purple`, `red`, `slate`).
- All 11 tables wrapped in `.table-wrap`.
- Deletes are strictly POST forms with CSRF tokens and confirm dialogs.

---

## 4. Performance Reviewer (`performance-reviewer`)

### Critical
- *None.*

### Important
- **PR-I1**: `apps/sales/forms/CustomerSuccess/CustomerOnboardings.py:65`, `CustomerRenewals.py:70`, `CustomerBusinessReviews.py:72` — Chained N+1 Queries in Form Choice Fields via `__str__` FK Hops: `SalesOrder.__str__` accesses `self.customer.name` and `AccountPlan.__str__` accesses `self.account`. Form field querysets (`sales_order`, `original_order`, `account_plan`) lack `.select_related("customer")` / `.select_related("account")`, triggering 1+N queries on form render. Fix: add `.select_related("customer")` to SalesOrder querysets and `.select_related("account")` to AccountPlan queryset.
- **PR-I2**: `apps/sales/views/CustomerSuccess/CustomerRenewals.py:200-208` and `templates/sales/customersuccess/renewal_pipeline.html:73, 78, 83` — Unnecessary QuerySet Evaluation via `|length` on Unevaluated QuerySets: `upcoming_30_days`, `upcoming_60_days`, `upcoming_90_days` are evaluated via `|length` in template, executing 3 full SQL queries with hydration just for row counts. Fix: consolidate the 3 interval counts into the existing `all_renewals.aggregate(...)` in view and reference `stats.upcoming_*_count`.
- **PR-I3**: `apps/sales/views/CustomerSuccess/CustomerBusinessReviews.py:229-238` — Multiple Separate Count Queries in `customer_advocacy_hub`: 4 separate `.count()` queries executed against `CustomerBusinessReview`. Fix: consolidate into a single `.aggregate()` call with conditional `Count("id", filter=Q(...))`.
- **PR-I4**: `apps/sales/models/CustomerSuccess/CustomerOnboardings.py:122`, `CustomerRenewals.py:132`, `CustomerBusinessReviews.py:150` — Missing Composite Database Indexes for Tenant-Scoped Status & Stage Filters: existing composite indexes have `account` preceding `status`/`stage`, which cannot accelerate filters on `(tenant, status)` or `(tenant, stage)`. Fix: add `Index(fields=["tenant", "status"], name="sales_cob_ten_stat_idx")`, `Index(fields=["tenant", "stage"], name="sales_crn_ten_stage_idx")`, and `Index(fields=["tenant", "status"], name="sales_qbr_ten_stat_idx")`.

### Minor
- **PR-M1**: `templates/sales/customersuccess/advocacy_hub.html:76` — Display Count Discrepancy from Sliced QuerySet: renders `{{ referenceable_accounts|length }}` where `referenceable_accounts` is sliced `[:15]`. Fix: change to `{{ stats.referenceable_count }}`.
- **PR-M2**: `templates/sales/customersuccess/renewal_pipeline.html:97-115` — Redundant Linear Dictionary Scans in Kanban Template: template nests lookup loops. Fix: prepare stage data structures in view.

### Strengths Noted
- Zero N+1 queries on core list and detail pages: all related foreign keys (`account`, `owner`, `csm`, `currency`, `original_order`, etc.) are eagerly loaded with `.select_related()`.
- Console headline metrics calculate all statistical summaries via single SQL `.aggregate()` queries.
- App-standard pagination (`Paginator(qs, 15)`) applied after GET filtering and sliced via SQL LIMIT/OFFSET.
- Seeder utilizes `.exists()` before each record creation.

---

## 5. QA Smoke Tester (`qa-smoke-tester`)

### Runtime Smoke Test Summary
- **Database Status**: Migrations verified, `seed_sales` verified idempotent across Acme Inc and Globex Corporation tenants.
- **URL Coverage**: Swept all 25 sub-module routes via Django in-process test client as `admin_acme` (5 Consoles/Hubs + 20 Model CRUD endpoints).
- **Template Cleanliness**: 100% free of comment leaks (`{#` or `{% comment` absent in all rendered HTML responses).
- **Cross-Tenant IDOR**: 12/12 cross-tenant requests (Detail GET, Edit GET, Delete POST against Globex objects while authenticated as Acme admin) correctly returned **404 Not Found**.
- **Junk Parameter Robustness**: 72/72 combinations of malicious/invalid query params (`?q=garbage!@#$`, `?page=abc`, `?page=9999`, `?page=-5`, `?status=invalid`, `?health_band=supergreen`, `?account=abc`) handled gracefully without a single 500 error.
- **Method Enforcement**: All 4 delete endpoints strictly reject GET requests with **405 Method Not Allowed** via `@require_POST`.

### URL Sweep Status Table
| URL Name | Method | Path | Status | Content / Assertions |
|---|---|---|---|---|
| `sales:customer_health_console` | GET | `/sales/customer-success/health-console/` | 200 OK | Title present, stats metrics populated, zero comment leaks |
| `sales:customer_renewal_pipeline` | GET | `/sales/customer-success/renewal-pipeline/` | 200 OK | Kanban stages present, ARR metrics rendered, zero comment leaks |
| `sales:customer_onboarding_hub` | GET | `/sales/customer-success/onboarding-hub/` | 200 OK | Milestones & stage breakdown rendered, zero comment leaks |
| `sales:customer_qbr_studio` | GET | `/sales/customer-success/qbr-studio/` | 200 OK | Strategic review schedule & account tiers rendered, zero comment leaks |
| `sales:customer_advocacy_hub` | GET | `/sales/customer-success/advocacy-hub/` | 200 OK | Reference accounts & advocacy metrics rendered, zero comment leaks |
| `sales:customer_health_score_list` | GET | `/sales/customer-success/health-scores/` | 200 OK | Page title, table wrap, status filters rendered, zero comment leaks |
| `sales:customer_health_score_detail` | GET | `/sales/customer-success/health-scores/<pk>/` | 200 OK | Record number token (e.g. `CHS-00001`), account link, badge color classes |
| `sales:customer_health_score_create` | GET | `/sales/customer-success/health-scores/create/` | 200 OK | Form inputs present, CSRF token verified, zero comment leaks |
| `sales:customer_health_score_edit` | GET | `/sales/customer-success/health-scores/<pk>/edit/` | 200 OK | Form populated with instance data, CSRF token, zero comment leaks |
| `sales:customer_health_score_delete` | GET / POST | `/sales/customer-success/health-scores/<pk>/delete/` | 405 GET / 500 POST | 405 on GET (@require_POST verified); POST crashes with 500 (see QA-C1) |
| `sales:customer_renewal_list` | GET | `/sales/customer-success/renewals/` | 200 OK | Page title, table wrap, stage filters rendered, zero comment leaks |
| `sales:customer_renewal_detail` | GET | `/sales/customer-success/renewals/<pk>/` | 200 OK | Record number token (`CRN-00003`), renewal terms, badge color classes |
| `sales:customer_renewal_create` | GET | `/sales/customer-success/renewals/create/` | 200 OK | Form inputs present, CSRF token verified, zero comment leaks |
| `sales:customer_renewal_edit` | GET | `/sales/customer-success/renewals/<pk>/edit/` | 200 OK | Form populated with instance data, CSRF token, zero comment leaks |
| `sales:customer_renewal_delete` | GET / POST | `/sales/customer-success/renewals/<pk>/delete/` | 405 GET / 500 POST | 405 on GET (@require_POST verified); POST crashes with 500 (see QA-C1) |
| `sales:customer_onboarding_list` | GET | `/sales/customer-success/onboardings/` | 200 OK | Page title, table wrap, onboarding stage filters, zero comment leaks |
| `sales:customer_onboarding_detail` | GET | `/sales/customer-success/onboardings/<pk>/` | 200 OK | Record number token (`COB-00003`), milestone timeline, badge classes |
| `sales:customer_onboarding_create` | GET | `/sales/customer-success/onboardings/create/` | 200 OK | Form inputs present, CSRF token verified, zero comment leaks |
| `sales:customer_onboarding_edit` | GET | `/sales/customer-success/onboardings/<pk>/edit/` | 200 OK | Form populated with instance data, CSRF token, zero comment leaks |
| `sales:customer_onboarding_delete` | GET / POST | `/sales/customer-success/onboardings/<pk>/delete/` | 405 GET / 500 POST | 405 on GET (@require_POST verified); POST crashes with 500 (see QA-C1) |
| `sales:customer_business_review_list` | GET | `/sales/customer-success/business-reviews/` | 200 OK | Page title, table wrap, review filters rendered, zero comment leaks |
| `sales:customer_business_review_detail` | GET | `/sales/customer-success/business-reviews/<pk>/` | 200 OK | Record number token (`QBR-00002`), stakeholder tags, badge classes |
| `sales:customer_business_review_create` | GET | `/sales/customer-success/business-reviews/create/` | 200 OK | Form inputs present, CSRF token verified, zero comment leaks |
| `sales:customer_business_review_edit` | GET | `/sales/customer-success/business-reviews/<pk>/edit/` | 200 OK | Form populated with instance data, CSRF token, zero comment leaks |
| `sales:customer_business_review_delete` | GET / POST | `/sales/customer-success/business-reviews/<pk>/delete/` | 405 GET / 500 POST | 405 on GET (@require_POST verified); POST crashes with 500 (see QA-C1) |

---

### Critical Findings
- **QA-C1** (Runtime Confirmation of CR-C1): `apps/sales/views/CustomerSuccess/CustomerHealthScores.py:111, 141, 167`, `CustomerRenewals.py:122, 151, 178`, `CustomerOnboardings.py:124, 152, 180`, `CustomerBusinessReviews.py:127, 155, 183` — HTTP 500 Internal Server Error verified on all POST write actions (Create, Edit, Delete). When submitting form creation or deletion, `write_audit_log(request.user, "CREATE", obj, ...)` triggers `ContentType.objects.get_for_model(obj.__class__)` where `obj` receives a string literal (`"CREATE"`), raising `AttributeError: type object 'str' has no attribute '_meta'`. Fix: correct parameter order to `write_audit_log(request.user, obj, "create", message, tenant=request.tenant)`.

### Important Findings
- **QA-I1** (Runtime Confirmation of CR-I1 / EX-I1): `templates/sales/customersuccess/customerrenewal/detail.html:133` and `templates/sales/customersuccess/customeronboarding/detail.html:135` — Linked sales order document numbers render silently blank. In seeded Acme records where a `SalesOrder` (`SO-00001`) is attached, the token `SO-00001` is absent from rendered HTML because templates evaluate `{{ obj.original_order.order_number }}` and `{{ obj.sales_order.order_number }}` instead of `.number`.
- **QA-I2** (Runtime Confirmation of CR-I2 / FE-I1): `templates/sales/customersuccess/customerhealthscore/detail.html:76, 78` — Broken template filter arithmetic on health score deltas. When `previous_score` exists (e.g. 70) and `overall_score` is 85, `{{ obj.overall_score|add:"-"|add:obj.previous_score }}` evaluates to empty string, rendering literally `(+)` without the numeric score delta (`+15`). Fix: define `@property def score_delta(self)` on `CustomerHealthScore` returning `self.overall_score - self.previous_score` and render `{{ obj.score_delta }}`.
- **QA-I3** (Runtime Confirmation of CR-I3): `templates/sales/customersuccess/customerhealthscore/detail.html:35`, `list.html:199`, and across all 4 entity templates — Delete buttons and forms are exposed to non-admin users. Verified with standard user `smoke_leaver`: delete forms/buttons are visible in HTML, but submitting them returns 403 `PermissionDenied` ("Tenant administrator access required"). Fix: guard delete actions with `{% if request.user.is_superuser or request.user.is_tenant_admin %}`.
- **QA-I4** (Runtime Confirmation of FE-I2): `templates/sales/customersuccess/customerhealthscore/list.html:234, 244` and `customerbusinessreview/list.html:234, 244` — Filter query parameter drop in pagination links. `customerhealthscore/list.html` drops `is_churn_risk`, and `customerbusinessreview/list.html` drops `template_type` and `is_referenceable` on page 2+ links.

### Minor Findings
- **QA-M1** (Runtime Confirmation of EX-M1): `apps/sales/views/CustomerSuccess/CustomerHealthScores.py:204` — Context key divergence: `customer_health_console` passes `"all_scores"` instead of contract-pinned `"health_scores"`.
- **QA-M2** (Runtime Confirmation of EX-M2): `apps/sales/views/CustomerSuccess/CustomerOnboardings.py:208` — Context key omission: `customer_onboarding_hub` omits top-level `"avg_ttv"`.

### Praise / Strengths
- **Flawless Multi-Tenant IDOR Protection**: 12/12 cross-tenant access attempts cleanly returned HTTP 404, validating strict tenant-scoped filtering on all detail, edit, and delete queries.
- **100% Clean HTML Responses**: Zero template comment leaks (`{#` or `{% comment`) found across all 25 tested routes.
- **Zero 500s on Junk Input**: Handled 72 junk query parameter combinations gracefully with zero crashes.
- **Clean HTTP Method Boundaries**: All 4 deletion endpoints properly require POST and return HTTP 405 on GET.

---

## 6. Security Reviewer (`security-reviewer`)

### Critical
- **SEC-C1** (Security confirmation of CR-C1 / QA-C1): `apps/sales/views/CustomerSuccess/CustomerHealthScores.py:111-116, 139-144, 167-172`, `CustomerRenewals.py:120-125, 148-153, 176-181`, `CustomerOnboardings.py:123-128, 150-155, 178-183`, `CustomerBusinessReviews.py:125-130, 153-158, 181-186` — Inverted parameter signature in `write_audit_log`: action string passed as `obj`, raising `AttributeError` and causing unhandled 500 on all state mutations, while completely preventing security audit logs from being recorded. Fix: swap to `write_audit_log(request.user, obj, action, message, tenant=request.tenant)`, calling before `obj.delete()`.

### Important
- **SEC-I1** (Security confirmation of CR-I3 / QA-I3): Administrative Action Exposure — Missing UI Authorization Gates: delete buttons and forms are unconditionally exposed to all standard users, returning 403 upon submission. Fix: wrap delete forms/buttons with `{% if request.user.is_superuser or request.user.is_tenant_admin %}`.

### Minor
- **SEC-M1** (Security confirmation of CR-M2): Computed metric field `time_to_value_days` exposed in `CustomerOnboardingForm.Meta.fields`. Fix: exclude from form fields and treat as read-only telemetry.

### Praise / Strengths
- Multi-Tenant Isolation & Anti-IDOR: 100% of querysets filter by `tenant=request.tenant`, and model instances use `get_object_or_404(Model.objects.filter(tenant=request.tenant), pk=pk)`.
- Form FK sanitization: All 4 forms inherit from `TenantUniqueMixin` and `TenantModelForm`, with choice querysets strictly scoped in `__init__` and double-guarded by `_reject_foreign` and model `clean()`.
- Zero CSRF or XSS exposures: 100% of POST forms include `{% csrf_token %}`, zero instances of `|safe`, `mark_safe`, or inline scripts.
- Safe redirects: All views redirect to static internal URL reversals using `<int:pk>`.

---

## 7. Consolidated Deduplicated Findings Register (Phase 5 Action Items)

| ID | Sev | Category | Location | Summary / Fix | Status |
|---|---|---|---|---|---|
| **C1** | Critical | Bug / Audit | `apps/sales/views/CustomerSuccess/*.py` (all 12 call sites) | Inverted parameter signature in `write_audit_log(request.user, "CREATE", obj, ...)`. Fix: `write_audit_log(request.user, obj, "create", message, tenant=request.tenant)`, and call before `obj.delete()` in deletion views. | [ ] open |
| **I1** | Important | Template / Data | `templates/sales/customersuccess/customerrenewal/detail.html:133` & `customeronboarding/detail.html:135` | `scm.SalesOrder` identifier field is `number`, not `order_number`. Fix: change `.order_number` to `.number`. | [ ] open |
| **I2** | Important | Template / Math | `templates/sales/customersuccess/customerhealthscore/detail.html:76, 78` | Invalid filter chaining `|add:"-"|add:...` evaluates to empty string. Fix: define `@property def score_delta(self)` on `CustomerHealthScore` model and render `{{ obj.score_delta }}`. | [ ] open |
| **I3** | Important | UI / RBAC | `templates/sales/customersuccess/*/{list,detail}.html` (all 4 entities) | Delete buttons/forms visible to non-admins but backend requires `@tenant_admin_required`. Fix: wrap with `{% if request.user.is_superuser or request.user.is_tenant_admin %}`. | [ ] open |
| **I4** | Important | Template / UX | `customerhealthscore/list.html` & `customerbusinessreview/list.html` | Pagination links drop active filters (`is_churn_risk`, `template_type`, `is_referenceable`). Fix: preserve all active filter parameters in pagination links. | [ ] open |
| **I5** | Important | Performance | `CustomerOnboardings.py:65`, `CustomerRenewals.py:70`, `CustomerBusinessReviews.py:72` | Chained N+1 queries in form choices via `__str__` FK hops. Fix: add `.select_related("customer")` on SalesOrder querysets and `.select_related("account")` on AccountPlan queryset. | [ ] open |
| **I6** | Important | Performance | `CustomerRenewals.py:200-208` & `renewal_pipeline.html:73, 78, 83` | Unnecessary full model hydration via `|length` on 3 unevaluated QuerySets. Fix: consolidate counts into `all_renewals.aggregate(...)` and use `{{ stats.upcoming_*_count }}`. | [ ] open |
| **I7** | Important | Performance | `CustomerBusinessReviews.py:229-238` | Multiple separate count queries in `customer_advocacy_hub`. Fix: consolidate into single `.aggregate()` call on `all_reviews`. | [ ] open |
| **I8** | Important | Performance | `CustomerOnboardings.py:122`, `CustomerRenewals.py:132`, `CustomerBusinessReviews.py:150` | Missing composite indexes on `(tenant, status)` and `(tenant, stage)`. Fix: add `sales_cob_ten_stat_idx`, `sales_crn_ten_stage_idx`, `sales_qbr_ten_stat_idx` in models and run `makemigrations` + `migrate`. | [ ] open |
| **M1** | Minor | Form / Telemetry | `CustomerOnboardings.py:26, 44` | Exclude computed `time_to_value_days` from `CustomerOnboardingForm.Meta.fields`. | [ ] open |
| **M2** | Minor | Contract | `CustomerHealthScores.py:204` | Context key drift in `customer_health_console`: pass `"health_scores": all_scores[:25]`. | [ ] open |
| **M3** | Minor | Contract | `CustomerOnboardings.py:208` | Context key omission in `customer_onboarding_hub`: pass top-level `"avg_ttv": stats.get("avg_ttv")`. | [ ] open |
| **M4** | Minor | Template / UX | `customerrenewal/list.html`, `customeronboarding/list.html`, `customerbusinessreview/list.html` | Add missing filter dropdowns for owner/CSM and playbook/template. | [ ] open |
| **M5** | Minor | Template / UX | `advocacy_hub.html:76` | Sliced queryset length display discrepancy: use `{{ stats.referenceable_count }}` instead of `|length`. | [ ] open |
| **M6** | Minor | Template / Safety | `onboarding_hub.html:119, 172`, `qbr_studio.html:134`, `advocacy_hub.html:104, 150` | Defensive None-safe formatting on `lead_csm`: wrap in `{% if rev.lead_csm %}` (L10). | [ ] open |
| **M7** | Minor | Accessibility / RTL | List templates and consoles | Add `aria-label` attributes to search/filter inputs, and use logical CSS classes (`border-s-*`, `ps-*`, `ms-*`). | [ ] open |





