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
