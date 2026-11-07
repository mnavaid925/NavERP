# Review Findings — Sub-module 10.16: Alerts, Subscriptions & Distribution (Module 10 — Business Intelligence, `bi`)

- **Sub-module:** 10.16 Alerts, Subscriptions & Distribution
- **App:** `apps/bi`
- **Review range:** `a3d989bc06eda3b74ce2a67a70785992ec94fca0...HEAD`
- **Date:** 2026-11-08
- **Reviewers:** `code-reviewer` -> `explorer` -> `frontend-reviewer` -> `performance-reviewer` -> `qa-smoke-tester` -> `security-reviewer`

---

## Consolidated Deduplicated Findings Register

### Critical Issues

- [x] **[C1] Non-Existent Theme Badge CSS Classes in Models & Templates (Rule L33 Violation)** — fixed in `71156fae`, `ec504ada`, `8061b423`, `62cbbc62` (replaced badge-blue and badge-purple with badge-info and badge-slate)
  - **Location:** `apps/bi/models/AlertsSubscriptions/BiAlertRules.py:198`, `BiNotificationItems.py:130,138,150,151`, `DistributionBurstRuns.py:112,122,123`, `ReportSubscriptions.py:170,171`
  - **Impact:** Model badge properties return invalid classes `badge-blue` and `badge-purple`. When rendered in templates (`bi_alert_rule/list.html`, `report_subscription/list.html`, `distribution_burst_run/list.html`, `bi_notification_item/list.html`, `notification_center.html`), the badges render unstyled without color or theme styling.
  - **Fix:** Replace all occurrences of `badge-blue` with `badge-info` and `badge-purple` with `badge-slate` or `badge-info`.

- [x] **[C2] Cross-Tenant User Exposure & Foreign Tenant Attachment (IDOR in Forms)** — fixed in `9190b120`, `e078ca83`, `a3596bdf` (scoped user querysets by self.tenant in form __init__ and validated with reject_foreign in clean)
  - **Location:** `apps/bi/forms/AlertsSubscriptions/BiAlertRules.py:80-97`, `BiNotificationItems.py:74-91`, `ReportSubscriptions.py:72-92`
  - **Impact:** ModelForms query `User.objects.all()` by default for FK and M2M fields (`recipient_users`, `recipient`, `subscriber_users`), rendering cross-tenant users in dropdowns and permitting cross-tenant user assignment via crafted POST payloads.
  - **Fix:** Filter user querysets by `self.tenant` in form `__init__` and validate with `reject_foreign(self, cleaned, [...])` in `clean()`.

- [x] **[C3] 500 Unhandled Template Crash on Null Foreign Key `subscription.created_by` (Rule L10 Violation)** — fixed in `afaf8183` (wrapped subscription.created_by in template if guard with fallback to System)
  - **Location:** `templates/bi/alerts_subscriptions/report_subscription/detail.html:201`
  - **Impact:** Accessing `{{ subscription.created_by.get_full_name|default:subscription.created_by.username }}` crashes with an unhandled 500 `AttributeError` when `created_by` is None.
  - **Fix:** Wrap with `{% if subscription.created_by %}{{ subscription.created_by.get_full_name|default:subscription.created_by.username }}{% else %}<span class="text-muted">System</span>{% endif %}`.

- [x] **[C4] Unhandled `ValueError` / DoS on Hand-Parsed `hours` in `notification_snooze` (Rule L35 Violation)** — fixed in `6c6f2fc1` (wrapped in try/except and bounded hours to allowed tuple (1, 4, 24, 72) with fallback 4)
  - **Location:** `apps/bi/views/AlertsSubscriptions/BiNotificationItems.py:328-334`
  - **Impact:** Hand-parsed `int(request.POST.get("hours", "4"))` crashes with 500 on non-digit or empty input, and accepts negative or huge integer values that corrupt scheduling state.
  - **Fix:** Wrap integer conversion in `try/except (ValueError, TypeError, OverflowError)` and validate duration within allowed set `(1, 4, 24, 72)` with fallback to 4.

---

### Important Issues

- [x] **[I1] Missing `<select name="status">` in Three List Filter Bars** — fixed in `ef8fc34f`, `70a373e9`, `8b8e3810` (added status select dropdowns and matching labels/ids to all three templates)
  - **Location:** `templates/bi/alerts_subscriptions/report_subscription/list.html:75-124`, `distribution_burst_run/list.html:75-115`, `bi_notification_item/list.html:75-115`
  - **Impact:** Backing views parse `request.GET.get("status")` and pass `status_choices` and `selected_status`, but templates omit the status `<select>` dropdown from their filter bars.
  - **Fix:** Add `<select name="status" id="filter-status" class="form-select">` with options from `status_choices` and `{% if selected_status == val %}selected{% endif %}`.

- [x] **[I2] Unvalidated Open Redirects in Notification Action Handlers** — fixed in `6779255e` (validated redirect targets using url_has_allowed_host_and_scheme in _safe_redirect)
  - **Location:** `apps/bi/views/AlertsSubscriptions/BiNotificationItems.py:280,319,339,367`
  - **Impact:** Action handlers redirect directly to unvalidated user-controlled `request.POST.get("next")` or `request.META.get("HTTP_REFERER")`, enabling phishing open redirects.
  - **Fix:** Validate redirect target using `url_has_allowed_host_and_scheme(url=next_url, allowed_hosts={request.get_host()}, require_https=request.is_secure())` via a `_safe_redirect` helper.

- [x] **[I3] Redundant Query & Inefficient M2M Count in `report_subscription_run_now`** — fixed in `c1965f30` (removed redundant prefetch and evaluated user count from cache)
  - **Location:** `apps/bi/views/AlertsSubscriptions/ReportSubscriptions.py:223-227`
  - **Impact:** Prefetches `["subscriber_users", "subscriber_org_units"]` but executes `subscription.subscriber_users.count()` which bypasses prefetch cache, and never uses `subscriber_org_units`.
  - **Fix:** Avoid unneeded `subscriber_org_units` prefetch and evaluate user count from prefetched cache via `len(subscription.subscriber_users.all())` (or omit prefetch and use `.count()`).

- [x] **[I4] Unnecessary Multi-Table `LEFT OUTER JOIN`s in Stat Card Aggregates** — fixed in `8494ca05`, `5fd5a90a`, `75115953`, `eed53dc3` (aggregated stats on clean base_qs before select_related)
  - **Location:** `apps/bi/views/AlertsSubscriptions/BiAlertRules.py:23`, `ReportSubscriptions.py:22`, `DistributionBurstRuns.py:24`, `BiNotificationItems.py:31`
  - **Impact:** `.select_related(...)` is called prior to `.aggregate()`, forcing unnecessary joins on stat count queries.
  - **Fix:** Execute `.aggregate()` on clean `base_qs` before applying `.select_related(...)` to the paginated list queryset.

- [x] **[I5] Missing `["tenant", "-created_at"]` Composite Index on Ordered Models** — fixed in `1843aff6`, `56b3366f`, `5d3bcb69` (added composite indexes and ran migration 0038)
  - **Location:** `apps/bi/models/AlertsSubscriptions/BiAlertRules.py:181`, `ReportSubscriptions.py:143`
  - **Impact:** Models order by `-created_at` in tenant-scoped queries without a composite index, causing database filesort.
  - **Fix:** Add `models.Index(fields=["tenant", "-created_at"], name="idx_balr_ten_created")` and `models.Index(fields=["tenant", "-created_at"], name="idx_bsub_ten_created")`.

- [x] **[I6] `seed_bi --flush` Routine Omits Sub-module 10.16 Models** — fixed in `81f86704` (added BiNotificationItem, DistributionBurstRun, ReportSubscription, BiAlertRule deletions to flush routine)
  - **Location:** `apps/bi/management/commands/seed_bi.py:98`
  - **Impact:** Running `manage.py seed_bi --flush` fails to delete `BiNotificationItem`, `DistributionBurstRun`, `ReportSubscription`, and `BiAlertRule`, leaving orphaned rows.
  - **Fix:** Add deletion calls for all four models at the start of the flush transaction.

- [x] **[I7] Potential Stored XSS via Pseudo-protocol Schemes in `action_url`** — fixed in `db18156a` (added clean_action_url restricting to relative paths or http/https)
  - **Location:** `apps/bi/forms/AlertsSubscriptions/BiNotificationItems.py:29`
  - **Impact:** `action_url` is rendered in template `href` attributes without scheme validation, allowing `javascript:` URLs.
  - **Fix:** Add `clean_action_url()` to `BiNotificationItemForm` restricting to relative paths (`/`) or `http://`/`https://` protocols.

- [x] **[I8] URL Route Aliases for Prompt/Contract Consistency** — fixed in `fd28c0f8`, `aeeec552` (added short route aliases for alert_rule_* and notification_item_*)
  - **Location:** `apps/bi/urls/AlertsSubscriptions/BiAlertRules.py`, `BiNotificationItems.py`
  - **Impact:** URL routes are registered as `bi:bi_alert_rule_*` and `bi:bi_notification_item_*`, whereas callers and navigation links may reference short aliases `bi:alert_rule_*` and `bi:notification_item_*`.
  - **Fix:** Register alias URL patterns in both route files to support both naming styles.

- [x] **[I9] Contract Alignment: Supply `users` in Form View Context** — fixed in `61442c03`, `c5688499`, `2cfb631e` (supplied tenant users queryset in context for create and edit form views)
  - **Location:** `apps/bi/views/AlertsSubscriptions/BiAlertRules.py:140-145,172-177`, `ReportSubscriptions.py:144-150,184-190`, `BiNotificationItems.py:202-207,240-245`
  - **Impact:** Pre-build contract specified `users` in the create/edit form context dictionaries.
  - **Fix:** Add `context["users"] = User.objects.filter(tenant=request.tenant).order_by("username")` in form views.

---

### Minor Issues

- [x] **[M1] Missing Audit Trail on Alert Snoozing** — fixed in `fa60d30e` (added write_audit_log in notification_snooze)
  - **Location:** `apps/bi/views/AlertsSubscriptions/BiNotificationItems.py:335`
  - **Impact:** Snoozing active alerts mutates status without generating an `AuditLog` entry.
  - **Fix:** Add `write_audit_log` call to `notification_snooze`.

- [x] **[M2] Missing `update_fields` on State Mutations in Action Handlers** — fixed in `d25c948e`, `0fd78b81` (specified update_fields in bi_alert_rule_test_evaluate and report_subscription_run_now)
  - **Location:** `apps/bi/views/AlertsSubscriptions/BiAlertRules.py:256`, `ReportSubscriptions.py:271`
  - **Impact:** Action handlers invoke `.save()` without `update_fields`, rewriting all table columns unnecessarily.
  - **Fix:** Provide explicit `update_fields` list matching the updated status and timestamp fields.

- [x] **[M3] Dead/Unused Querysets in View Context** — fixed in `2cbe4769` (removed unused recent_burst_runs from bi_alert_rule_detail context)
  - **Location:** `apps/bi/views/AlertsSubscriptions/BiAlertRules.py:100-104`, `ReportSubscriptions.py:140-150`
  - **Impact:** Dead context variables (`recent_burst_runs`, etc.) constructed but never referenced in templates.
  - **Fix:** Clean up unused view context keys.

- [x] **[M4] Raw Format Identifier `HTML_INLINE` Rendered in Report Subscription Templates** — fixed in `64714270`, `d2d2641c` (rendered human-readable HTML badge label instead of raw identifier)
  - **Location:** `templates/bi/alerts_subscriptions/report_subscription/list.html:176`, `report_subscription/detail.html:17`
  - **Impact:** Format choice `html_inline` renders directly as `HTML_INLINE` instead of a human-readable label.
  - **Fix:** Render `{{ s.get_export_format_display }}` or human-readable "HTML".

- [x] **[M5] Missing Label `for` and Input `id` Attribute Associations in Filter Forms** — fixed in `ef8fc34f`, `70a373e9`, `8b8e3810`, `38578590`, `e585a643` (added matching for/id attributes across all filter controls)
  - **Location:** `templates/bi/alerts_subscriptions/**/*.html` list templates
  - **Impact:** Filter labels lack `for="filter-<name>"` matching `id="filter-<name>"` on `<select>` elements.
  - **Fix:** Add matching `for` and `id` attributes across all filter controls.

- [x] **[M6] Static Metric on Critical Priority Stat Card in Notification Center** — fixed in `77aee821`, `4198f7f3` (computed critical_count aggregate and rendered in stat card)
  - **Location:** `templates/bi/alerts_subscriptions/notification_center.html:50`
  - **Impact:** Card renders static text "Active" instead of dynamic count because `critical_count` was omitted from context.
  - **Fix:** Compute `critical_count` in `notification_center` view and render `{{ critical_count }}` in template.

- [x] **[M7] Missing `aria-label` on Icon-Only Action Buttons** — fixed in `a645659c`, `23ab903d`, `f5dd7ecc`, `aa17872e`, `0e1c32e8` (added aria-label attributes matching title on all icon-only buttons and links)
  - **Location:** `templates/bi/alerts_subscriptions/**/*.html` list and notification center templates
  - **Impact:** Action buttons include `title` attributes but lack explicit `aria-label` attributes for accessibility.
  - **Fix:** Add `aria-label` matching `title` on icon-only buttons and links.

- [x] **[M8] Document Runtime / Advanced Status for Form-Excluded JSON Fields** — fixed in `33f84ad8`, `de4e95b8` (documented intentional omission of filter_overrides and burst_slicing_metadata in form docstrings)
  - **Location:** `apps/bi/forms/AlertsSubscriptions/ReportSubscriptions.py:14`, `DistributionBurstRuns.py:15`
  - **Impact:** `filter_overrides` and `burst_slicing_metadata` are managed dynamically by system execution rather than user form inputs.
  - **Fix:** Add explicit docstrings explaining their intentional omission from standard CRUD forms.

- [x] **[M9] Restrict Destructive Model Deletions to Tenant Admins** — fixed in `9bcfa08a`, `e1a76f89`, `7bc31441` (added @tenant_admin_required decorator to all deletion views)
  - **Location:** `apps/bi/views/AlertsSubscriptions/BiAlertRules.py:181`, `ReportSubscriptions.py:196`, `DistributionBurstRuns.py:191`
  - **Impact:** Deletion of tenant-level alert rules, subscriptions, and burst runs should require administrative privileges.
  - **Fix:** Add `@tenant_admin_required` decorator to deletion views.
