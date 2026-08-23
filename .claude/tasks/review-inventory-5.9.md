# Review — inventory 5.9 Order Management & Fulfillment

Changeset `2c7dee77..HEAD` (22 commits): FulfillmentWave [WAV-] + FulfillmentWaveOrder,
verb lifecycle (release/close/cancel), computed wave_board, CRUD quintet admin-gated,
migration 0014 (bundles pending 5.10 tables — shared checkout, disclosed), wiring hunks.

## Lane coverage

| Lane | Result |
|---|---|
| code-reviewer (contract/conventions) | network-failed x2 — remaining checks run INLINE in main session (contract values verbatim vs scm.SalesOrder; wave_ref linkage real+indexed; LIVE_LINKS titles verbatim; urls order safe) + 1 finding (M6) |
| frontend-reviewer | FE-1 Important, FE-2/FE-3 Minor |
| qa-smoke-tester | QA-C1 Critical, QA-C2 Critical, QA-O1 note; DB restored |
| security-reviewer | SEC-1 High (=C2), SEC-2 Low, SEC-3 Low, SEC-4 Low (=I2) |
| performance-reviewer | PERF-1 Important (=I1), PERF-2 Minor |

No lane left uncovered — the failed lane's checklist was executed inline and produced M6.

## Findings (fix in ID order)

### Critical

- [x] **C1** — `forms/FulfillmentOrchestration/FulfillmentWaves.py` — POSTing the same sales
      order into a wave twice returns **500 IntegrityError** (unique_together ("wave","sales_order")
      never form-checked: `wave` is not a form field so validate_unique skips the constraint).
      Row count survives but the endpoint 500s for any logged-in member.
      **Fix:** explicit duplicate check in `FulfillmentWaveOrderForm.clean()` (lookup
      FulfillmentWaveOrder.objects.filter(wave=instance.wave_id, sales_order=cleaned sales_order)
      excluding instance pk), error keyed `__all__`. Verify: duplicate POST re-renders with error,
      no 500, count unchanged.
      *Fixed (0114c37a) — error "That sales order is already in this wave." keyed `__all__`; QA probe: second POST 302 flash, count unchanged, no 500.*
- [x] **C2** — `views/FulfillmentOrchestration/FulfillmentWaves.py:136-151` — wave_release /
      wave_close / wave_cancel carry only @login_required + @require_POST: **any member can flip
      any wave's lifecycle via crafted POST** (QA-verified escalation), contradicting the module
      docstring and the 5.3/5.4 gating spec. **Fix:** add @tenant_admin_required to all three verb
      views; verify member POST -> 403 and admin still succeeds.
      *Fixed (8737388f) — all three verbs gated; QA 4b: non-admin release -> 403, status stays planned; admin lifecycle still green.*

### Important

- [x] **I1** — list page N+1 (~45 queries/page at 15 rows): template renders `w.orders.count` +
      `pick_progress_pct` (evaluated twice) per row. **Fix:** annotate `member_count=Count("orders")`
      on the list qs (template renders the annotation), compute pick stats ONCE per page via the
      board's grouped merge and pass `{pk: pct}` through extra_context (fall back to property only
      when absent). Template switches to `w.member_count` / dict lookup. Verify: CaptureQueriesContext
      on GET /inventory/waves/ flat regardless of row count (report number).
      *Fixed (d05d9c67 + cd7ce50d + a4017b11) — shared `_pick_stats_by_ref()` helper now behind board AND list; annotate() had dropped Meta ordering, restated. Query count: 20 at 2 rows, 20 at 32 rows (flat).*
- [x] **I2** — seed_inventory --flush deletes 5.10 tables but not FulfillmentWave/FulfillmentWaveOrder;
      flushed tenants keep stale waves forever (exists()-guard then skips). **Fix:** add both tables to
      flush count + delete block, membership rows first. Verify: --flush then seed creates fresh waves.
      *Fixed (2110c009) — live-verified: `--flush` removed 261 rows incl. both wave tables, reseed created "2 fulfillment waves" per tenant, second run skips.*

### Minor

- [x] **M1** — `FulfillmentWaveOrder.clean()` guards sales_order tenant but not wave tenant (non-form
      writers could pair cross-tenant wave). Fix: id-based wave.tenant check keyed "wave".
      *Fixed (6094e4e2).*
- [x] **M2** — `templates/inventory/fulfillment/wave/detail.html:98` renders `m.added_at`; field is
      `created_at` — Added-At column silently blank. Fix binding (+ date filter like siblings).
      *Fixed (67b0b0cf) — binds `m.created_at|date:"M d, Y H:i"`.*
- [x] **M3** — list rows render Edit affordance regardless of status; gate `{% if w.is_editable %}`
      matching detail-page behavior (server already refuses).
      *Fixed (1127f13e).*
- [x] **M4** — board filter bar lacks the `q` input the view supports; add text input mirroring list.
      *Fixed (4e6c8ccf) — echoes `{{ q }}` like list.html.*
- [x] **M5** — detail evaluates `obj.pick_progress_pct` up to 3x (3 identical aggregates); hoist once
      into view context (`pick_pct`) and bind template to it.
      *Fixed (29350147 + 2ce3c8bb).*
- [x] **M6** — seeder `_seed_fulfillment_waves` uses `is_staff=True` lookup only; a tenant with no
      staff user passes `admin=None` into `wave.release(None)` (audit write risk). Broaden fallback:
      staff first, else any tenant user (sibling line-769 pattern).
      *Fixed (dcb7bd00) — staff-first/any-user fallback plus a None guard that leaves the wave planned instead of releasing with no author.*

### Accepted-as-is

- Deleting closed waves allowed — documented design choice (views comment; QA-O1 consistent).
- Migration 0014 bundles ReturnsManagement (5.10) tables — shared-checkout reality, disclosed in commit.
- Board omits nothing else: status/location/q all functional server-side (M4 adds the missing affordance only).

## Verification bar for the fixer

After each code finding: `manage.py check` clean. Final gates: `temp/smoke_fulfillment_5_9.py`
ALL PASS; C1+C2 probes from `temp/qa_fulfillment_5_9.py` re-run clean (duplicate POST renders
error; member verb POST 403); post-I1 list-page query count reported. Commits one file per commit;
mark findings `[x] fixed` / `[~] skipped — reason` in this file; docs commit at end.
