# Review — Inventory 5.2 Vendor / Supplier Management

- Changeset: `28f1efae..HEAD` (24 commits) · Date: 2026-08-22
- Lanes: code-reviewer · explorer/wiring · frontend-reviewer · performance-reviewer · qa-smoke-tester · security-reviewer (parallel)
- Lane results: explorer OK · frontend OK · security OK · code 4M · perf 1I+1M(+1 no-action) · qa 1I

| ID | Sev | Finding | Status |
|----|-----|---------|--------|
| M1 | M | `__str__` renders `None` for an unsaved/party-less row | [x] fixed |
| M2 | M | `is_follow_up_overdue` used `date.today()`; view filter uses `timezone.localdate()` — midnight divergence risk (L16 convention) | [x] fixed |
| M3 | M | Seeder derived follow-up dates from UTC `.date()` instead of `localdate()` | [x] fixed |
| M4 | M | `TenantNumbered.save()` falls through to an unguarded save after exhausted retries | [~] skipped — verbatim copy of the accepted scm/app-wide base; fixing here would fork five sibling apps' shared pattern. Tracked with the app-wide sequence-table hardening noted in `next_number` |
| P-I1 | I | Detail siblings queryset carries a dead `select_related("party")` (template never dereferences it) | [x] fixed |
| P-M1 | M | No index backs the default `-occurred_at` ordering → per-request filesort on an unbounded log | [x] fixed (index `inv_vc_tnt_occur_idx`, migration 0004) |
| P-I2 | I | `?direction` filter unindexed | [~] skipped — 2-value cardinality; optimizer would ignore the index anyway (codebase norm) |
| Q-I1 | I | Cross-tenant vendor POST shows generic `invalid_choice` copy instead of "another workspace" (queryset narrowing rejects before `_reject_foreign` runs) | [~] skipped — by-design parity: every sibling form in every app behaves identically via `TenantModelForm` narrowing; security outcome identical (reject, nothing saved, no foreign data leaked) |

Post-fix verification: `makemigrations` 0004 applied · `manage.py check` clean · full smoke suite re-run green (all pages 200, IDOR 404s intact, no leak markers).
