# Review — 0.17 Monitoring, Logging & Observability

**BASE:** `320670bb` · **Scope:** `apps/core/`, `templates/core/`, `.claude/tasks/*0.17*`
**Reviewers:** `code-reviewer` → `explorer` (run so far, strictly one at a time).

All findings below are **fixed and committed**, each in its own commit. Verification after every batch:
`manage.py check` clean, the 16-page smoke (content asserted, not just status), and
`temp/audit_integrity.py` 6/6 PASS.

---

## Critical

- [x] **C1 — `healthboard.html:44` read `status_choices`, which `health_board` never passed.** The
  `{% for %}` iterated zero times, so the "Status counts" card rendered **empty at HTTP 200** — the
  L7/L8 blank-region failure a smoke test cannot see. A second bug on the same line:
  `{{ status_counts|default_if_none:0 }}` printed the whole dict per label, because a Django template
  cannot index a dict by a loop variable. → `58b8e0d9`, `7d74b209`. **Verified:** the card now renders
  `Operational: 1 · Degraded: 1 · Partial outage: 0 · Major outage: 0 · Unknown: 1`, no raw dict leaks.
- [x] **C2 — `firingboard.html:52-53` read `state_choices` / `severity_choices`, neither passed.**
  Both summary lines rendered as bare labels followed by nothing. → `58b8e0d9`, `8e9eb623`. Fixed by
  the same `state_rows` / `severity_rows` zip.
- [x] **C3 — `alert_event_list` declared a `?rule=` filter with no UI to set it, and omitted the
  contract-pinned `rules` key.** Reachable only by hand-typing a URL. → `26be5364`, `b9b3d552`.
- [x] **C4 — `AlertRule.__str__` called `get_metric_display()` on a field named `metric_key`.** This
  raised `AttributeError` inside every `ModelChoiceField` that labels an `AlertRule`, crashing the
  `AlertEvent` **create form** outright. Caught by the smoke test, not `manage.py check`. → `aee25144`.

## Important

- [x] **I1 — `AlertEventForm.save()` overwrote `service_label` unconditionally**, so clearing the
  service (a legitimate correction) set the snapshot to `""` and destroyed the very evidence meant to
  outlive the component. → `996a252a`.
- [x] **I2 — `capacity_board` joined a rule's bound to a usage row by DISPLAY LABEL.** The two
  `METRIC_CHOICES` vocabularies overlap but label differently, so the join silently never matched.
  → `58b8e0d9`, now joins on the raw `metric_key`.
- [x] **I3 — `capacity_board` hard-coded a `gte` sign and never read `comparator`.** A seeded
  `comparator="lt"` rule reported "within the declared bound" for exactly the readings that breach it,
  and the board never printed the operator. → `26be5364`, `c6bda7e3`. Now branches on `gt/gte` vs
  `lt/lte`, and reports **no** headroom for a non-ordering operator rather than inventing a number.
- [x] **I4 — `AlertRule.clean()` never checked tier order**, so `warning 100 / critical 50` was
  accepted; the board then picked the looser `critical` tier as "the bound" and called a breach
  healthy. → `7a53e13d`. **Verified:** reversed `gte` and reversed `lt` pairs are now REJECTED, correct
  pairs ACCEPTED, and a two-tier rule on `eq` is REJECTED as non-ordering.
- [x] **I5 — `is_active` (register membership) was used as "still open"** on the incident list, so a
  resolved-but-unarchived incident was called open and an archived-but-open one vanished. → `26be5364`,
  `97d81f83`. `open_count` and `active_count` are now separate keys.
- [x] **I6 — one register, two denominators, and a false "No components registered."** The health board
  counts only active components while the overview counted every row; with everything retired the health
  board claimed nothing was registered. → `26be5364`, `5fd420f8`. `_STATUS_SEVERITY.index()` (a 500 on
  any unrecognised status) replaced with a rank lookup defaulting to `unknown`.

## Minor

- [x] **M1 — `alert_rule_detail` ran three queries over the same rows.** Collapsed into
  `_rule_event_stats()`, one ordered fetch. → `58b8e0d9`.
- [x] **M2 — `status_note` / `bounds_note` / `measure_note` were methods, not properties**, so
  `{% if obj.status_note %}` was always true (Django returns a bound method, which is truthy).
  `status_note`'s docstring also promised a `None` return it never had. → `cd1eb9e3`.
- [x] **M3 — `firing_count` was computed every render and never displayed**, while the contract's
  `open_count` / `total_count` were missing. → `58b8e0d9`, `046de801`.
- [x] **M4 — the seeder's demo data contradicted itself**: "Payments API latency budget" was attached to
  the **database** component and "Database storage headroom" to the **web front end**. → `b1085fca`.
- [x] **M5 — two `LIVE_LINKS["0.17"]` labels resolved to the same URL as two others**, so four sidebar
  labels covered two pages and the active-link highlight lit two entries at once. → `e0f78862`. Now
  **8 of 8 distinct** and all reversing.
- [x] **M6 — `owner_role_name` was a property nothing read** (a promise the next agent would trust).
  Removed; `is_scheduled` was instead surfaced on the incident detail where it belongs. → `cd1eb9e3`,
  `24bfdda7`.
- [x] **M7 — the incident list computed `active_count` and rendered no banner**, unlike its two
  siblings. → `97d81f83`.

## Phase 4 — later passes

### `frontend-reviewer`

- [x] **F1 (Critical) — the alert-event badge ladder omitted `no_data` and `expired`**, dumping both into
  the `{% else %}` grey that means "unrecognised value". `no_data` is the *loud* condition (the metric
  stopped reporting — silence, not health) and rendered as the quietest row on the page. →
  `d438cad2`, `546d1201`.
- [x] **F2 (Critical) — the incident status ladder covered 4 of the 8-value union enum.** `investigating`,
  `identified` and `in_progress` — an outage *in progress*, the exact opposite of resolved — rendered in
  the same grey as a value the model cannot hold. → `20c5c67d`, `4b9d55e5`.
- [x] **F3 — the health board's status card keyed its badges off the DISPLAY LABEL** while the other four
  ladders keyed off the raw value, so one `STATUS_CHOICES` relabel would grey out that one card. The
  zip now carries the value as a third element. → `794f9262`, `35a9d1d9`.
- [x] **F4 — the resolution-note input had no accessible name** (a placeholder is not one). →
  `546d1201`.
- [x] **F5 — the health board's empty state dropped the retired/never-registered distinction** its own
  banner makes. → `35a9d1d9`.

### `performance-reviewer`

- [x] **P1 (Critical) — `IncidentForm.primary_alert` was an N+1: 200 events rendered 201 queries.**
  `AlertEvent.__str__` dereferences `self.rule`, and `TenantModelForm` scopes the queryset without
  joining it. **Verified fixed: the page now costs 10 queries with 30 firings.** → `9831ed92`.
- [x] **P2 (Critical) — `_rule_event_stats` loaded a rule's entire firing history to derive three
  scalars** (measured 0.711 s / 20,000 instances at 20k rows, vs 0.031 s for an aggregate — 23x). Now a
  database aggregate. → `84f6c0a6`.
- [x] **P3 — four separate `COUNT`s on the alert-event list** collapsed into one `aggregate()`. →
  `84f6c0a6`, `af9158a3`.
- [x] **P4 — the capacity board loaded every `UsageRecord` ever written** to keep the newest per metric.
  Capped at 200, ordered newest-first. → `84f6c0a6`.

### `qa-smoke-tester` — 387/396 assertions passing

Every failure traced to **one** cause: the contract pinned context keys the build had renamed. The
**build was correct; the contract was stale.** Critical band: **none** — no cross-tenant leak, no
missing CRUD, no blank page, no 500 on junk input. Verified clean: content on 16/16 pages, junk
params and pagination 89/89, cross-tenant 44/44, authorization 45/45, POST-only actions 26/26, CRUD
42/42, admin 41/41, and the tenant returned to exactly its starting state.

- [x] **Q1 — contract §5.6 pinned `component_count` / `rule_count`;** the build uses `component_total` /
  `rule_total` (plus the retired/active split). A test written to the old pin would `KeyError`. → `1e900ae6`.
- [x] **Q2 — contract §5.4 pinned three flat count keys;** the build ships one `event_totals` aggregate
  dict. → `1e900ae6`.
- [x] **Q3 — contract §5.5 pinned `incident_type_choices`;** the build uses `type_choices`, matching the
  `?type=` GET param. → `1e900ae6`.
- [x] **Q4 — contract §5.6 pinned `firing_events`;** the build passes `open_events` (capped, with
  `open_total`). → `1e900ae6`.
- [x] **Q5 — the contract file's own structure was broken** (§5.4–5.6 had been appended after §9, and
  §2.4's body was orphaned). Repaired. → `1e900ae6`.

### `security-reviewer` — run in-session, read-only, with live probes

The sub-agent channel began returning auth errors, so this pass was run directly rather than skipped.
**Critical / High: none.** Verified by probe, not by reading:

- **Tenant escape at the form layer — the highest-value check.** Posting a *Globex-owned* pk as
  `AlertRule.service`, `AlertEvent.rule` and `Incident.affected_services` (the M2M) was **rejected in
  all three cases** — "Select a valid choice. That choice is not one of the available choices." The
  control (the same field with the caller's own pk) validates, so the rejection is scoping, not a
  broken field. `TenantModelForm` narrows `ModelMultipleChoiceField` as well as `ModelChoiceField`.
- **`crud_detail` / `crud_delete` filter on `tenant=request.tenant` by construction** (`crud.py`), so no
  0.17 view can be handed a foreign queryset.
- **Mass assignment — blocked.** A crafted edit POST carrying `tenant`/`tenant_id` (Globex),
  `fired_at`, `first_seen_at`, `last_seen_at`, `acknowledged_at`, `resolved_at` and `is_active` left
  the row on `acme`, left `fired_at` untouched, and did **not** set `resolved_at`. The forms' explicit
  `Meta.fields` are what does this.
- **POST-only action state transitions are validated server-side**: resolving an already-resolved event
  is a no-op (302, state unchanged); recurring a settled event does not increment.
- **`resolution_note` is length-validated server-side** — a 400-character POST stored exactly 255, so
  the widget's `maxlength` is not the only guard.
- **XSS: no `|safe`, no `{% autoescape off %}`, no `mark_safe`** anywhere in the 16 templates or the
  three 0.17 modules.
- **Admin**: all 4 models registered; every declared system stamp is `readonly_fields` (including all
  seven `AlertEvent` lifecycle fields, so an admin cannot attribute an acknowledgement to somebody who
  did not make it).

**Two observations recorded, NOT fixed here — both are pre-existing repo-wide, not 0.17 regressions:**

- **`403` is returned before the `404` lookup**, so a non-admin member can distinguish "a row with this
  pk exists" from "it does not". This is the house convention: `@tenant_admin_required` raises
  `PermissionDenied` (`apps/core/decorators.py:19`) and is used on **1,464 views across 12 apps**.
  Changing it is a repo-wide decision for the owner, not a 0.17 fix.
- **Django-admin is not tenant-scoped.** 0.17's 4 registrations follow every other admin in the repo:
  only 2 of `core`'s 60 `ModelAdmin` classes define a tenant-filtering `get_queryset`. A Django
  superuser can therefore see all tenants — the same as for 0.1–0.16.


---

## Known, accepted (not defects)

- **`AlertRule.frequency` reuses `SyncSchedule.FREQUENCY_CHOICES` by reference and is not an FK.**
  Deliberate: nothing runs it. **Flagged for 0.20** — the Admin Console sub-module will either add a
  `schedule` FK alongside it or migrate the column. Reuse-by-reference at least means a new 0.13 choice
  propagates instead of forking.
- **`TenantConsistentMixin` does not tenant-check the `Incident.affected_services` M2M on the admin
  path** (it walks `ForeignKey`/`OneToOneField` only; `TenantModelForm` narrows M2M on the form path).
  Same posture as 0.16's escalated C7. **`TenantModelForm` was deliberately not changed** — it would
  break committed tests in three other apps. Must be recorded in `SKILL.md` at close-out.
- **`AlertEvent` and `Incident` are not seeded** (L52). They are evidence of things NavERP did not
  observe. The Acme tenant therefore has zero of each, which is why the smoke script creates and deletes
  its own rows in a `try/finally`. **Do not "fix" this by seeding them.**

## All six reviewers have run

`code-reviewer` → `explorer` → `frontend-reviewer` → `performance-reviewer` → `qa-smoke-tester` →
`security-reviewer`, strictly one at a time. **No finding is left open.** The last four passes were
recorded above rather than under the earlier heading; the sub-agent channel began returning auth
errors partway through, so the `security-reviewer` pass was executed in-session with live probes
instead of being skipped.

**Not tested (stated, not assumed):** the >200-firing truncation warning and the 20,000-row claim were
not exercised against the live shared database — the histogram `values().annotate(Count)` shape was
confirmed present, not benchmarked. The 0.12 seam (`AlertRule.notification_rule`) and the 0.8/0.13
board links were not re-exercised. `seed_core` idempotency was verified earlier and not re-run here,
to avoid writing to the shared dev DB.

- [x] **I7 — three pages materialised whole tables to count them in Python**, unbounded;
  `firing_board` loaded every firing ever recorded. → `26be5364`, `a7e568d8`. Histograms are now grouped
  `values().annotate(Count)` and the open list is capped at 200 with an explicit "this is truncated"
  warning.
