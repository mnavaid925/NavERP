# Test contract — `apps/dashboard` (the untested app)

**Created:** 2026-09-21 · **Plan:** `plan-remaining-5-housekeeping.md` Item A
**App:** `apps/dashboard` — the only app in the repo with no test lane
**Lanes:** **two, not four.** The app has **no models and no forms of its own** (`apps.py`, `urls.py`,
`views.py`, `migrations/__init__.py`), so a `_models` or `_forms` lane would be an empty file.

---

## Why this app is worth testing despite being tiny

`views.home` is the **root landing page every authenticated user hits**, and it holds real logic that a
regression would break *silently* — the worst kind:

| logic | how it fails silently |
|---|---|
| `tenant = request.tenant` + `if tenant is not None:` | without the guard, the no-tenant path raises instead of rendering zeroed stats |
| latest-value-per-metric via `Max("id")` subquery | an edit can return the **wrong row** rather than erroring — the classic silent-wrong-answer query |
| six cross-app aggregates (`core.Party`, `core.PartyRole`, `core.Activity`, `core.AuditLog`, `tenants.Subscription`, `tenants.SubscriptionInvoice`) | dropping a `tenant=` filter leaks another workspace's counts into the page |
| `dict(PartyRole.ROLE_CHOICES)` / `dict(Activity.STATUS_CHOICES)` with `.get(raw, raw)` | a chart label list can silently drift out of step with its data list |
| `recent_audit` capped at 8 | an unbounded query grows the landing page without failing |

---

## Fixtures — measured, not assumed

**Baseline from the ROOT `conftest.py`** (probed with `temp/probe_dashboard_baseline.py`, 2026-09-21):

| tenant | users | active users | everything else |
|---|---|---|---|
| `tenant_a` (`acme`) | **2** (`admin_acme`, `member_acme`) | **2** | **0** — no parties, roles, activities, audit, health, subscriptions or invoices |
| `tenant_b` (`globex`) | **0** | **0** | **0** |

So the root fixtures create **only the two users**; every other figure below is created by this app's
own conftest. That is why the expected numbers are exact rather than "greater than zero".

> **CORRECTION (measured 2026-09-21, after the first run failed).** The "2 users" row is true only if
> `member_user` is *requested*. pytest fixtures are **lazy**, and the first draft of
> `test_user_counts_equal_the_seeded_figures` asked for `client_a` alone — so tenant_a held only its own
> `admin_acme` and the count read **1**. Probed with `temp/probe_dashboard_lane.py`, which requests
> exactly what the lane requests. The fix is to name `member_user` in the test signature, so the premise
> is explicit rather than an artefact of which fixture happened to be pulled in.
> **Rule: any exact-count assertion must first confirm the fixture is actually in the graph.**

**Root fixtures reused as-is:** `tenant_a`, `tenant_b`, `admin_user`, `member_user`, `client_a`,
`client_b`, `member_client`.

**Fixtures this lane adds** (`apps/dashboard/tests/conftest.py`), each creating rows in **both** tenants
so the isolation test has something real to exclude:

| fixture | tenant_a | tenant_b | purpose |
|---|---|---|---|
| `dash_parties` | 3 parties | 2 parties | `parties_count` must be 3, never 5 |
| `dash_party_roles` | 2× `customer`, 1× `supplier` | 1× `customer` | grouped chart: 2 rows, `customer` first (`order_by("-c")`) |
| `dash_activities` | 2× `open`, 1× `done` | 1× `open` | grouped chart: 2 rows, ordered by `status` |
| `dash_health` | metric `users` **twice** (values 10 then 99) + `storage_mb` once | 1 row | **the `Max("id")` subquery's whole point** — 99 must win |
| `dash_audit` | **10** rows | 3 rows | `recent_audit` must be capped at **8**, newest first |
| `dash_subscription` | **2** subscriptions | 1 | `stats["subscription"]` must be the **newest** |
| `dash_invoices` | 2 `open` + 1 `paid` | 1 `open` | `open_invoices` must be **2**, not 3 or 4 |

### The two determinism problems, and how the fixtures solve them

1. **"Newest subscription" cannot rely on `created_at` ties.** `Subscription.created_at` is
   `auto_now_add`, so two rows created in the same test can carry the same timestamp and the view's
   `order_by("-created_at").first()` becomes non-deterministic. The fixture creates the older row, then
   **`Subscription.objects.filter(pk=…).update(created_at=<earlier>)`** — `update()` bypasses
   `auto_now_add` — then creates the newer one. Deterministic, and it exercises the ordering the view
   actually does.
2. **"Latest health row" is deterministic by `pk`** because `Max("id")` is what the view uses. The
   fixture asserts nothing about time; it relies on the higher id, which is exactly the contract.

---

## Lanes and their exact expectations

### `apps/dashboard/tests/test_dashboard_views.py`

| # | test | expectation |
|---|---|---|
| 1 | `test_home_renders_for_an_authenticated_tenant_user` | `client_a` GET `dashboard:home` → **200**, template `dashboard/home.html` |
| 2 | `test_user_counts_equal_the_seeded_figures` | `stats["users_count"] == 2`, `stats["active_users"] == 2` — **requires naming `member_user`** (see the correction above) |
| 3 | `test_party_count_is_tenant_scoped` | `stats["parties_count"] == 3` (tenant_a's 3, **not** 5) |
| 4 | `test_open_invoice_count_counts_only_open` | `stats["open_invoices"] == 2` (the `paid` one excluded) |
| 5 | `test_subscription_is_the_newest` | `stats["subscription"].pk == <the newer one>` |
| 6 | `test_role_chart_groups_and_orders_by_count_desc` | labels `["Customer", "Supplier"]` (display strings, not raw values), data `[2, 1]` |
| 7 | `test_activity_chart_groups_and_orders_by_status` | data sums to 3; labels are display strings |
| 8 | `test_chart_label_and_data_lists_are_the_same_length` | for **both** charts — the drift guard |
| 9 | `test_latest_health_row_per_metric_wins_by_max_id` | `users` row present with value **99** (not 10); `storage_mb` present once; `health` length == 2 |
| 10 | `test_recent_audit_is_capped_at_eight_and_newest_first` | `len(recent_audit) == 8`; `recent_audit[0]` is the newest of the 10 |
| 11 | `test_chart_label_falls_back_to_the_raw_value` | an unknown role/status value renders as itself, not as `None` (the `.get(raw, raw)` guard) |

### `apps/dashboard/tests/test_dashboard_security.py`

| # | test | expectation |
|---|---|---|
| 1 | `test_anonymous_is_redirected_to_login` | an anonymous GET → **302** with `/login` in `Location`, **not** 200 |
| 2 | `test_tenant_isolation_of_the_aggregates` | `client_a` sees tenant_a's figures only: parties **3** not 5, open invoices **2** not 3, `len(recent_audit) == 8` from tenant_a's 10 (tenant_b's 3 never appear) |
| 3 | `test_no_tenant_renders_zeroed_stats` | the superuser `admin` (whose `tenant` is **None** by design) → **200** with every stat `0` / `None`, and no exception. **This is the `if tenant is not None:` guard's whole purpose.** |
| 4 | `test_no_tenant_returns_empty_charts` | same request: `health == []`, `recent_audit == []`, both chart label/data lists empty |

> **Test 3 needs a tenant-less user.** The repo's superuser `admin` has `tenant=None` by design (every
> seeder prints a warning about it), so the fixture is `User.objects.create_superuser(...)` with no
> tenant — created locally in the security lane, not in conftest, because it is that lane's premise.

---

## Out of scope (stated, not omitted)

- **No template assertions beyond the template name.** `templates/dashboard/home.html` is covered by the
  audit's template-existence check and by the 7.x template conventions; asserting its markup here would
  duplicate that and break on any cosmetic edit.
- **No query-count assertion.** The view's aggregates are already narrow; pinning a query count would
  make an unrelated optimisation fail this lane. If a count is ever wanted it belongs in a
  `performance-reviewer` pass, not here.

## Mutation probe — a green lane is not evidence

Run 2026-09-21. `apps/dashboard/views.py` was backed up to `temp/views_dashboard_backup.py`, three
defects were injected, the lane re-run, and the file restored (hashes compared — identical, empty
`git diff`). **Each injected defect was caught by exactly the tests that exist to catch it, and by no
others** — so the lane discriminates rather than merely passing:

| injected defect | tests that failed |
|---|---|
| `Party.objects.filter(tenant=tenant)` → `Party.objects.count()` (leaks the tenant filter) | `test_party_count_is_tenant_scoped`, `test_tenant_isolation_of_the_aggregates` |
| `Max("id")` → `Min("id")` in the health subquery | `test_latest_health_row_per_metric_wins_by_max_id` |
| `recent_audit` cap `[:8]` → `[:10]` | `test_recent_audit_is_capped_at_eight_and_newest_first` |

**Incident worth recording:** the first mutation attempt issued four `Edit` calls against the *same*
file in one message. They raced and **lost two of the four changes** — the result imported `Min` while
still calling `Max`, so every request 500'd and 12 tests failed. That looked like a broken test lane and
was not: it was a broken *edit*. Mutate one file with **sequential** edits, and always sanity-check the
mutated file's own consistency (imports vs. usage) before reading anything into a red run.

---

## Gate

```bash
venv\Scripts\python.exe -m pytest apps/dashboard/tests --nomigrations -p no:cacheprovider --junitxml=temp/junit_dashboard.xml
```
Then `temp/audit_integrity.py` — **all 6 checks must still pass**; a new test lane must not disturb them.
