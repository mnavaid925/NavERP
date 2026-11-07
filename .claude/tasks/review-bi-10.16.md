# Review Findings — Sub-module 10.16: Alerts, Subscriptions & Distribution (Module 10 — Business Intelligence, `bi`)

- **Sub-module:** 10.16 Alerts, Subscriptions & Distribution
- **App:** `apps/bi`
- **Review range:** `a3d989bc06eda3b74ce2a67a70785992ec94fca0...HEAD`
- **Date:** 2026-11-08
- **Reviewers:** `code-reviewer` -> `explorer` -> `frontend-reviewer` -> `performance-reviewer` -> `qa-smoke-tester` -> `security-reviewer`

---

## Consolidated Deduplicated Findings Register

### Critical Issues

- [ ] **[C1] Non-Existent Theme Badge CSS Classes in Models & Templates (Rule L33 Violation)**
  - **Location:** `apps/bi/models/AlertsSubscriptions/BiAlertRules.py:198`, `BiNotificationItems.py:130,138,150,151`, `DistributionBurstRuns.py:112,122,123`, `ReportSubscriptions.py:170,171`
  - **Impact:** Model badge properties return invalid classes `badge-blue` and `badge-purple`. When rendered in templates (`bi_alert_rule/list.html`, `report_subscription/list.html`, `distribution_burst_run/list.html`, `bi_notification_item/list.html`, `notification_center.html`), the badges render unstyled without color or theme styling.
  - **Fix:** Replace all occurrences of `badge-blue` with `badge-info` and `badge-purple` with `badge-slate` or `badge-info`.

- [ ] **[C2] Cross-Tenant User Exposure & Foreign Tenant Attachment (IDOR in Forms)**
  - **Location:** `apps/bi/forms/AlertsSubscriptions/BiAlertRules.py:80-97`, `BiNotificationItems.py:74-91`, `ReportSubscriptions.py:72-92`
  - **Impact:** ModelForms query `User.objects.all()` by default for FK and M2M fields (`recipient_users`, `recipient`, `subscriber_users`), rendering cross-tenant users in dropdowns and permitting cross-tenant user assignment via crafted POST payloads.
  - **Fix:** Filter user querysets by `self.tenant` in form `__init__` and validate with `reject_foreign(self, cleaned, [...])` in `clean()`.

- [ ] **[C3] 500 Unhandled Template Crash on Null Foreign Key `subscription.created_by` (Rule L10 Violation)**
  - **Location:** `templates/bi/alerts_subscriptions/report_subscription/detail.html:201`
  - **Impact:** Accessing `{{ subscription.created_by.get_full_name|default:subscription.created_by.username }}` crashes with an unhandled 500 `AttributeError` when `created_by` is None.
  - **Fix:** Wrap with `{% if subscription.created_by %}{{ subscription.created_by.get_full_name|default:subscription.created_by.username }}{% else %}<span class="text-muted">System</span>{% endif %}`.

- [ ] **[C4] Unhandled `ValueError` / DoS on Hand-Parsed `hours` in `notification_snooze` (Rule L35 Violation)**
  - **Location:** `apps/bi/views/AlertsSubscriptions/BiNotificationItems.py:328-334`
  - **Impact:** Hand-parsed `int(request.POST.get("hours", "4"))` crashes with 500 on non-digit or empty input, and accepts negative or huge integer values that corrupt scheduling state.
  - **Fix:** Wrap integer conversion in `try/except (ValueError, TypeError, OverflowError)` and validate duration within allowed set `(1, 4, 24, 72)` with fallback to 4.

---

### Important Issues

- [ ] **[I1] Missing `<select name="status">` in Three List Filter Bars**
  - **Location:** `templates/bi/alerts_subscriptions/report_subscription/list.html:75-124`, `distribution_burst_run/list.html:75-115`, `bi_notification_item/list.html:75-115`
  - **Impact:** Backing views parse `request.GET.get("status")` and pass `status_choices` and `selected_status`, but templates omit the status `<select>` dropdown from their filter bars.
  - **Fix:** Add `<select name="status" id="filter-status" class="form-select">` with options from `status_choices` and `{% if selected_status == val %}selected{% endif %}`.

- [ ] **[I2] Unvalidated Open Redirects in Notification Action Handlers**
  - **Location:** `apps/bi/views/AlertsSubscriptions/BiNotificationItems.py:280,319,339,367`
  - **Impact:** Action handlers redirect directly to unvalidated user-controlled `request.POST.get("next")` or `request.META.get("HTTP_REFERER")`, enabling phishing open redirects.
  - **Fix:** Validate redirect target using `url_has_allowed_host_and_scheme(url=next_url, allowed_hosts={request.get_host()}, require_https=request.is_secure())` via a `_safe_redirect` helper.

- [ ] **[I3] Redundant Query & Inefficient M2M Count in `report_subscription_run_now`**
  - **Location:** `apps/bi/views/AlertsSubscriptions/ReportSubscriptions.py:223-227`
  - **Impact:** Prefetches `["subscriber_users", "subscriber_org_units"]` but executes `subscription.subscriber_users.count()` which bypasses prefetch cache, and never uses `subscriber_org_units`.
  - **Fix:** Avoid unneeded `subscriber_org_units` prefetch and evaluate user count from prefetched cache via `len(subscription.subscriber_users.all())` (or omit prefetch and use `.count()`).

- [ ] **[I4] Unnecessary Multi-Table `LEFT OUTER JOIN`s in Stat Card Aggregates**
  - **Location:** `apps/bi/views/AlertsSubscriptions/BiAlertRules.py:23`, `ReportSubscriptions.py:22`, `DistributionBurstRuns.py:24`, `BiNotificationItems.py:31`
  - **Impact:** `.select_related(...)` is called prior to `.aggregate()`, forcing unnecessary joins on stat count queries.
  - **Fix:** Execute `.aggregate()` on clean `base_qs` before applying `.select_related(...)` to the paginated list queryset.

- [ ] **[I5] Missing `["tenant", "-created_at"]` Composite Index on Ordered Models**
  - **Location:** `apps/bi/models/AlertsSubscriptions/BiAlertRules.py:181`, `ReportSubscriptions.py:143`
  - **Impact:** Models order by `-created_at` in tenant-scoped queries without a composite index, causing database filesort.
  - **Fix:** Add `models.Index(fields=["tenant", "-created_at"], name="idx_balr_ten_created")` and `models.Index(fields=["tenant", "-created_at"], name="idx_bsub_ten_created")`.

- [ ] **[I6] `seed_bi --flush` Routine Omits Sub-module 10.16 Models**
  - **Location:** `apps/bi/management/commands/seed_bi.py:98`
  - **Impact:** Running `manage.py seed_bi --flush` fails to delete `BiNotificationItem`, `DistributionBurstRun`, `ReportSubscription`, and `BiAlertRule`, leaving orphaned rows.
  - **Fix:** Add deletion calls for all four models at the start of the flush transaction.

- [ ] **[I7] Potential Stored XSS via Pseudo-protocol Schemes in `action_url`**
  - **Location:** `apps/bi/forms/AlertsSubscriptions/BiNotificationItems.py:29`
  - **Impact:** `action_url` is rendered in template `href` attributes without scheme validation, allowing `javascript:` URLs.
  - **Fix:** Add `clean_action_url()` to `BiNotificationItemForm` restricting to relative paths (`/`) or `http://`/`https://` protocols.

- [ ] **[I8] URL Route Aliases for Prompt/Contract Consistency**
  - **Location:** `apps/bi/urls/AlertsSubscriptions/BiAlertRules.py`, `BiNotificationItems.py`
  - **Impact:** URL routes are registered as `bi:bi_alert_rule_*` and `bi:bi_notification_item_*`, whereas callers and navigation links may reference short aliases `bi:alert_rule_*` and `bi:notification_item_*`.
  - **Fix:** Register alias URL patterns in both route files to support both naming styles.

- [ ] **[I9] Contract Alignment: Supply `users` in Form View Context**
  - **Location:** `apps/bi/views/AlertsSubscriptions/BiAlertRules.py:140-145,172-177`, `ReportSubscriptions.py:144-150,184-190`, `BiNotificationItems.py:202-207,240-245`
  - **Impact:** Pre-build contract specified `users` in the create/edit form context dictionaries.
  - **Fix:** Add `context["users"] = User.objects.filter(tenant=request.tenant).order_by("username")` in form views.

---

### Minor Issues

- [ ] **[M1] Missing Audit Trail on Alert Snoozing**
  - **Location:** `apps/bi/views/AlertsSubscriptions/BiNotificationItems.py:335`
  - **Impact:** Snoozing active alerts mutates status without generating an `AuditLog` entry.
  - **Fix:** Add `write_audit_log` call to `notification_snooze`.

- [ ] **[M2] Missing `update_fields` on State Mutations in Action Handlers**
  - **Location:** `apps/bi/views/AlertsSubscriptions/BiAlertRules.py:256`, `ReportSubscriptions.py:271`
  - **Impact:** Action handlers invoke `.save()` without `update_fields`, rewriting all table columns unnecessarily.
  - **Fix:** Provide explicit `update_fields` list matching the updated status and timestamp fields.

- [ ] **[M3] Dead/Unused Querysets in View Context**
  - **Location:** `apps/bi/views/AlertsSubscriptions/BiAlertRules.py:100-104`, `ReportSubscriptions.py:140-150`
  - **Impact:** Dead context variables (`recent_burst_runs`, etc.) constructed but never referenced in templates.
  - **Fix:** Clean up unused view context keys.

- [ ] **[M4] Raw Format Identifier `HTML_INLINE` Rendered in Report Subscription Templates**
  - **Location:** `templates/bi/alerts_subscriptions/report_subscription/list.html:176`, `report_subscription/detail.html:17`
  - **Impact:** Format choice `html_inline` renders directly as `HTML_INLINE` instead of a human-readable label.
  - **Fix:** Render `{{ s.get_export_format_display }}` or human-readable "HTML".

- [ ] **[M5] Missing Label `for` and Input `id` Attribute Associations in Filter Forms**
  - **Location:** `templates/bi/alerts_subscriptions/**/*.html` list templates
  - **Impact:** Filter labels lack `for="filter-<name>"` matching `id="filter-<name>"` on `<select>` elements.
  - **Fix:** Add matching `for` and `id` attributes across all filter controls.

- [ ] **[M6] Static Metric on Critical Priority Stat Card in Notification Center**
  - **Location:** `templates/bi/alerts_subscriptions/notification_center.html:50`
  - **Impact:** Card renders static text "Active" instead of dynamic count because `critical_count` was omitted from context.
  - **Fix:** Compute `critical_count` in `notification_center` view and render `{{ critical_count }}` in template.

- [ ] **[M7] Missing `aria-label` on Icon-Only Action Buttons**
  - **Location:** `templates/bi/alerts_subscriptions/**/*.html` list and notification center templates
  - **Impact:** Action buttons include `title` attributes but lack explicit `aria-label` attributes for accessibility.
  - **Fix:** Add `aria-label` matching `title` on icon-only buttons and links.

- [ ] **[M8] Document Runtime / Advanced Status for Form-Excluded JSON Fields**
  - **Location:** `apps/bi/forms/AlertsSubscriptions/ReportSubscriptions.py:14`, `DistributionBurstRuns.py:15`
  - **Impact:** `filter_overrides` and `burst_slicing_metadata` are managed dynamically by system execution rather than user form inputs.
  - **Fix:** Add explicit docstrings explaining their intentional omission from standard CRUD forms.

- [ ] **[M9] Restrict Destructive Model Deletions to Tenant Admins**
  - **Location:** `apps/bi/views/AlertsSubscriptions/BiAlertRules.py:181`, `ReportSubscriptions.py:196`, `DistributionBurstRuns.py:191`
  - **Impact:** Deletion of tenant-level alert rules, subscriptions, and burst runs should require administrative privileges.
  - **Fix:** Add `@tenant_admin_required` decorator to deletion views.
