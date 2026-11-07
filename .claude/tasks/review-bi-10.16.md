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
