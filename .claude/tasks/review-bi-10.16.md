# Review Findings — Sub-module 10.16: Alerts, Subscriptions & Distribution (Module 10 — Business Intelligence, `bi`)

- **Sub-module:** 10.16 Alerts, Subscriptions & Distribution
- **App:** `apps/bi`
- **Review range:** `a3d989bc06eda3b74ce2a67a70785992ec94fca0...HEAD`
- **Date:** 2026-11-07
- **Reviewers:** `code-reviewer` -> `explorer` -> `frontend-reviewer` -> `performance-reviewer` -> `qa-smoke-tester` -> `security-reviewer`

---

## 1. Code Reviewer Findings

### Critical
None.

### Important
1. `templates/bi/alerts_subscriptions/report_subscription/detail.html:201` — Optional nullable `created_by` foreign key is dereferenced inside filter arguments without an `{% if subscription.created_by %}` guard (`{{ subscription.created_by.get_full_name|default:subscription.created_by.username }}`), causing a 500 template error when `created_by` is None (Lesson L10). Fix: Wrap with `{% if subscription.created_by %}...{% else %}<span class="text-muted">System</span>{% endif %}`.
2. `apps/bi/views/AlertsSubscriptions/BiNotificationItems.py:329` — Hand-parsed integer from `request.POST.get("hours", "4")` without `try/except ValueError` or digit validation will raise an unhandled `ValueError` 500 crash on malformed/non-digit input (Lesson L35). Fix: Guard with `try/except (ValueError, TypeError)` or check `.isdigit()` and default to 4.
3. `templates/bi/alerts_subscriptions/distribution_burst_run/list.html:75` — Filter bar completely omits the `status` dropdown even though `distribution_burst_run_list` parses `request.GET.get("status")` and passes `status_choices` and `selected_status` in context. Fix: Add `<select name="status">` populated from `status_choices` with `{% if selected_status == val %}selected{% endif %}`.
4. `templates/bi/alerts_subscriptions/bi_notification_item/list.html:75` — Filter bar completely omits the `status` dropdown even though `bi_notification_item_list` parses `request.GET.get("status")` and passes `status_choices` and `selected_status` in context. Fix: Add `<select name="status">` populated from `status_choices` with `{% if selected_status == val %}selected{% endif %}`.
5. `apps/bi/management/commands/seed_bi.py:98` — `seed_bi --flush` routine omits all four Sub-module 10.16 models (`BiNotificationItem`, `DistributionBurstRun`, `ReportSubscription`, `BiAlertRule`), leaving orphaned records with severed foreign keys when re-seeding after flush. Fix: Add deletion statements for the 4 models at the top of the `--flush` atomic block.

### Minor
1. `apps/bi/models/AlertsSubscriptions/BiAlertRules.py:199`, `ReportSubscriptions.py:172`, `DistributionBurstRuns.py:123`, `BiNotificationItems.py:151` — Model badge helper properties specify `badge-blue` and `badge-purple` which do not exist in `static/css/theme.css` (only `badge-green`, `badge-red`, `badge-amber`, `badge-info`, `badge-muted`, `badge-slate` exist per Lesson L33). Fix: Map to `badge-info` and `badge-slate` / `badge-muted`.
2. `apps/bi/views/AlertsSubscriptions/BiNotificationItems.py:280,319,339,367` — Post-action redirects use unvalidated `request.POST.get("next") or request.META.get("HTTP_REFERER")`. Fix: Validate target URL with `url_has_allowed_host_and_scheme(next_url, allowed_hosts={request.get_host()})` or fallback to `bi:notification_center`.
3. `apps/bi/forms/AlertsSubscriptions/ReportSubscriptions.py:14` — `filter_overrides` field was specified in the pre-build contract form fields list but excluded from `ReportSubscriptionForm.Meta.fields`. Fix: Document intentional exclusion or add field with a JSON textarea widget.

---

## 2. Explorer Review Findings

### Critical
None.

### Important
1. `templates/bi/alerts_subscriptions/report_subscription/list.html:75-125` — The list filter bar completely omits the `<select name="status">` dropdown even though `report_subscription_list` parses `request.GET.get("status")`, passes `status_choices` and `selected_status` in context, checks `selected_status` in reset logic, and preserves `&status={{ selected_status }}` in pagination links. This matches the same filter omission present in `distribution_burst_run/list.html:75` and `bi_notification_item/list.html:75`. Fix: Add `<select name="status" class="form-select">` populated from `status_choices` with `{% if selected_status == val %}selected{% endif %}`.
2. `apps/bi/views/AlertsSubscriptions/BiAlertRules.py:140-145,172-177`, `ReportSubscriptions.py:144-150,184-190`, `BiNotificationItems.py:202-207,240-245` — Pre-build contract sections 4.1, 4.2, and 4.4 specifically pin `users` in the form view context dictionaries (`FK querysets: ... users`). In all three views (`bi_alert_rule_create`/`edit`, `report_subscription_create`/`edit`, `bi_notification_item_create`/`edit`), `users` was omitted from `context`. Fix: Pass tenant-scoped or active user queryset into `context["users"]`.
3. `templates/bi/alerts_subscriptions/report_subscription/detail.html:201` — Optional nullable foreign key `subscription.created_by` is dereferenced inside a template filter argument without an `{% if subscription.created_by %}` guard (`{{ subscription.created_by.get_full_name|default:subscription.created_by.username }}`), causing a template crash when `created_by` is None (Lesson L10). Fix: Wrap with `{% if subscription.created_by %}...{% else %}<span class="text-muted">System</span>{% endif %}`.

### Minor
1. `apps/bi/forms/AlertsSubscriptions/DistributionBurstRuns.py:15` — `burst_slicing_metadata` JSONField was listed in the pre-build contract Section 2.3 form fields list but omitted from `DistributionBurstRunForm.Meta.fields`. Fix: Add field with JSON textarea widget or document intentional omission for runtime automated logging.
2. `apps/bi/forms/AlertsSubscriptions/ReportSubscriptions.py:14` — `filter_overrides` JSONField was listed in the contract Section 2.2 form fields list but omitted from `ReportSubscriptionForm.Meta.fields`. Fix: Add field with JSON textarea widget or document as advanced API-only override.
3. `apps/bi/models/AlertsSubscriptions/BiAlertRules.py:199`, `ReportSubscriptions.py:172`, `DistributionBurstRuns.py:123`, `BiNotificationItems.py:151` — Model badge helper properties (`severity_badge_class`, `format_badge_class`, `channel_badge_class`, `category_badge_class`) map choices to `badge-blue` and `badge-purple`, which do not exist in `static/css/theme.css` (only `badge-green`, `badge-red`, `badge-amber`, `badge-info`, `badge-muted`, `badge-slate` exist per Lesson L33). Fix: Replace `badge-blue` with `badge-info` and `badge-purple` with `badge-slate` / `badge-indigo`.
4. `apps/bi/forms/AlertsSubscriptions/BiAlertRules.py:80`, `ReportSubscriptions.py:72`, `BiNotificationItems.py:74` — In forms, `recipient_users`, `subscriber_users`, and `recipient` are FK/M2M relationships to `settings.AUTH_USER_MODEL`. Filter by tenant in form `__init__`.
5. `apps/bi/management/commands/seed_bi.py:98` — The `seed_bi --flush` routine omits all four Sub-module 10.16 models (`BiNotificationItem`, `DistributionBurstRun`, `ReportSubscription`, `BiAlertRule`), risking orphaned records when flushing and re-seeding. Fix: Add deletion statements for the 4 models at the top of the `--flush` atomic block.

---

## 3. Frontend Reviewer Findings

### Critical
1. `apps/bi/models/AlertsSubscriptions/BiAlertRules.py:198`, `BiNotificationItems.py:130,138,150,151`, `DistributionBurstRuns.py:112,122,123`, `ReportSubscriptions.py:170,171` — Theme badge helper methods return invalid non-existent CSS classes `badge-blue` and `badge-purple`. When rendered in templates (`bi_alert_rule/list.html:182`, `report_subscription/list.html:175`, `distribution_burst_run/list.html:162,174`, `bi_notification_item/list.html:150,155,160`, and `notification_center.html:139,140`), the badges render unstyled without color (Lesson L33). Fix: Replace all occurrences of `badge-blue` with `badge-info` and `badge-purple` with `badge-slate` or `badge-info`.

### Important
1. `templates/bi/alerts_subscriptions/report_subscription/list.html:75-124`, `distribution_burst_run/list.html:75-115`, `bi_notification_item/list.html:75-115` — Filter forms in all three list templates omit `<select name="status">` dropdown even though the views parse `request.GET.get("status")` and pass `status_choices` and `selected_status` in context, and templates preserve `&status={{ selected_status }}` in pagination links. Fix: Add the missing `<select name="status">` dropdown populated from `status_choices` with `{% if selected_status == val %}selected{% endif %}`.
2. `templates/bi/alerts_subscriptions/report_subscription/detail.html:201` — Nullable foreign key `subscription.created_by` rendered inside a template filter expression without an `{% if subscription.created_by %}` guard (`{{ subscription.created_by.get_full_name|default:subscription.created_by.username }}`), causing 500 template error when null (Lesson L10). Fix: Guard with `{% if subscription.created_by %}...{% else %}<span class="text-muted">System</span>{% endif %}`.

### Minor
1. `templates/bi/alerts_subscriptions/report_subscription/list.html:176`, `report_subscription/detail.html:17` — Raw format value `html_inline` rendered directly in uppercase as `HTML_INLINE`. Fix: Render human-readable label using `{{ s.get_export_format_display }}` or `{% if s.export_format == 'html_inline' %}HTML{% else %}{{ s.export_format|upper }}{% endif %}`.
2. `templates/bi/alerts_subscriptions/bi_alert_rule/list.html:87,97,107`, `report_subscription/list.html:87,97,107`, `distribution_burst_run/list.html:87,97`, `bi_notification_item/list.html:87,97` — Filter `<label>` elements lack `for="filter-<name>"` matching `id="filter-<name>"` on the corresponding `<select>` elements. Fix: Add matching `for` and `id` attributes for accessibility.
3. `templates/bi/alerts_subscriptions/notification_center.html:50` — Critical Priority stat card renders static text `<div class="text-2xl font-bold text-rose-600">Active</div>` instead of dynamic count. Fix: Compute `critical_count` in `notification_center` view context and render `{{ critical_count }}`.
4. `templates/bi/alerts_subscriptions/bi_alert_rule/list.html:204,208,211,216`, `report_subscription/list.html:197,201,204,209`, `distribution_burst_run/list.html:185,188,193`, `bi_notification_item/list.html:168,171,176`, `notification_center.html:192,197` — Action buttons and icon links have `title` but lack explicit `aria-label` attributes. Fix: Add `aria-label` matching `title`.

---

## 4. Performance Reviewer Findings

### Critical
None.

### Important
1. `apps/bi/views/AlertsSubscriptions/ReportSubscriptions.py:223-227` — `report_subscription_run_now` prefetches `["subscriber_users", "subscriber_org_units"]`, but immediately calls `subscription.subscriber_users.count()`, which bypasses the prefetch cache and executes a duplicate `SELECT COUNT(*)` query. In addition, `subscriber_org_units` is prefetched but never used. Fix: Avoid unused prefetch in action handler and use in-memory `len(subscription.subscriber_users.all())` or remove prefetch and use `.count()`.
2. `apps/bi/views/AlertsSubscriptions/BiAlertRules.py:23-32`, `ReportSubscriptions.py:22-31`, `DistributionBurstRuns.py:24-33`, `BiNotificationItems.py:31-40` — In all four list views, `.select_related(...)` is called on `qs` before executing `.aggregate(...)` for stat cards, causing Django ORM to generate unnecessary multi-table `LEFT OUTER JOIN`s during count aggregation. Fix: Run aggregate count query on clean `base_qs` without `select_related`, and apply `select_related` only to the paginated list queryset.
3. `apps/bi/models/AlertsSubscriptions/BiAlertRules.py:181-186`, `ReportSubscriptions.py:143-148` — Both models order by `["-created_at"]` and list queries filter by tenant, but neither model defines a composite index on `["tenant", "-created_at"]` (causing filesort on large datasets). Fix: Add `models.Index(fields=["tenant", "-created_at"], name="idx_balr_ten_created")` and `models.Index(fields=["tenant", "-created_at"], name="idx_bsub_ten_created")` to `Meta.indexes`.

### Minor
1. `apps/bi/views/AlertsSubscriptions/BiAlertRules.py:100-104,137-145`, `ReportSubscriptions.py:140-150` — Dead context querysets (`recent_burst_runs`, `kpi_definitions`, `anomalies`, `dashboards`, `reports`, `org_units`) are constructed and passed to template contexts where they are never rendered. Fix: Clean up unused context variables.
2. `apps/bi/views/AlertsSubscriptions/BiAlertRules.py:256`, `ReportSubscriptions.py:271` — State mutations in action handlers invoke `.save()` without `update_fields`, rewriting all fields. Fix: Add explicit `update_fields` list matching the updated fields.

---

## 5. QA Smoke Tester Findings

### Critical
1. `templates/bi/alerts_subscriptions/report_subscription/detail.html:201` — Accessing a `ReportSubscription` where `created_by=None` raises `AttributeError: 'NoneType' object has no attribute 'username'`, crashing the detail page with HTTP 500 (Lesson L10). Fix: Guard with `{% if subscription.created_by %}{{ subscription.created_by.get_full_name|default:subscription.created_by.username }}{% else %}<span class="text-muted">System</span>{% endif %}`.
2. `apps/bi/views/AlertsSubscriptions/BiNotificationItems.py:329` — `hours = int(request.POST.get("hours", "4"))` without error handling raises `ValueError` 500 server crash when `hours` is malformed or empty string (Lesson L35). Fix: Wrap with `try/except (ValueError, TypeError)` or validate `.isdigit()`.

### Important
1. URL Name Consistency: URL routes registered in `BiAlertRules.py` and `BiNotificationItems.py` use `bi:bi_alert_rule_*` and `bi:bi_notification_item_*`. If short aliases (`bi:alert_rule_*`, `bi:notification_item_*`) are expected by callers, add alias paths to prevent `NoReverseMatch`.

### Minor
None.

---
