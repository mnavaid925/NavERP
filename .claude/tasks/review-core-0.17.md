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

## Still to run

`frontend-reviewer` → `performance-reviewer` → `qa-smoke-tester` → `security-reviewer`.

- [x] **I7 — three pages materialised whole tables to count them in Python**, unbounded;
  `firing_board` loaded every firing ever recorded. → `26be5364`, `a7e568d8`. Histograms are now grouped
  `values().annotate(Count)` and the open list is capped at 200 with an explicit "this is truncated"
  warning.
