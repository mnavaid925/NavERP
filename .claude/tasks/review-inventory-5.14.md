# Review findings — inventory 5.14 Barcode & RFID Integration

Range: `458f8e94...HEAD` scoped to BarcodeRfidIntegration paths + templates/inventory/barcode + shared-file 5.14 blocks · Generated: 2026-08-24
Wave (parallel): code-reviewer · explorer(contract) · frontend-reviewer · performance-reviewer · qa-smoke-tester · security-reviewer
Runtime at wave time: smoke_barcode.py ALL PASS (35 checks) · extended sweep 2 root-cause failures found (now C1/M2).

## Summary

| Severity | Count |
|---|---|
| Critical | 1 |
| Important | 6 |
| Minor | 16 |
| **Total (deduped)** | **23** |

| Agent | Raw findings |
|---|---|
| code-reviewer | 8 |
| explorer | 7 |
| qa-smoke-tester | 3 (2 unique defects + 1 stale-comment) |
| security-reviewer | 3 |
| frontend-reviewer | 7 |
| performance-reviewer | 2 |

## How to work this file (code-fixer)

Fix in ID order: `C1`, then `I1..I6`, then `M1..M16`. One fix → one file → one `git add` + one `git commit`.
Update each **Status** line to `[x] fixed — <commit subject>` or `[~] skipped — <reason>`. Never delete a
finding. Never `git push`.

**Scope guard:** a sibling session may still be building 5.12/5.13 tests in this checkout — touch ONLY files
named here (+ their package `__init__.py` blocks if exports change). Never edit `MultiLocationManagement/`,
never rewrite shared files wholesale. **Migration rule:** I5 needs a new migration — BEFORE generating, run
`Get-ChildItem apps/inventory/migrations -Name` and claim the next free number in your commit message
(`0019` unless taken). Verify each batch with:
`venv\Scripts\python.exe manage.py check`, `temp\smoke_barcode.py` (expect ALL PASS), and after I5 also
`manage.py migrate inventory` + seed idempotence.

## Critical

### C1 — `apps/inventory/views/BarcodeRfidIntegration/RfidTags.py`

- **Found by:** qa-smoke-tester (reproduced: activate-no-target → HTTP 500 NameError)
- **Problem:** module never imports `ValidationError`; every lifecycle-refusal path (`except ValidationError`)
  raises NameError → 500 instead of flash+redirect. DB stays correct but operators get error pages on any
  illegal transition (activate w/o target, double-activate, mark-lost off-active, retire-on-retired).
- **Fix:** add `from django.core.exceptions import ValidationError`.
- **Status:** [x] fixed — fix(inventory): 5.14 C1 import ValidationError in RfidTags views - lifecycle refusals flashed instead of NameError 500

## Important

### I1 — `apps/inventory/views/BarcodeRfidIntegration/ScanSessions.py:175`

- **Found by:** code-reviewer + explorer (both)
- **Problem:** console discards the resolved kind from `resolve_code()` — every recorded event gets
  `resolved_kind="unknown"` even when `ok=True`; console + session-detail badges mislabel matched scans.
  The seeder already calls `record(..., kind=kind, obj=obj)` correctly.
- **Fix:** capture `_kind, obj = resolve_code(...)` and pass `kind=_kind`.
- **Status:** [x] fixed — fix(inventory): 5.14 I1 console passes resolve_code kind into ScanEvent.record - matched scans no longer labelled unknown

### I2 — `apps/inventory/views/BarcodeRfidIntegration/ScanSessions.py` GET + `templates/inventory/barcode/console.html`

- **Found by:** code-reviewer + explorer + frontend (three lanes)
- **Problem:** list/detail "Open Console" links append `?session={pk}` but GET never reads it and the
  session `<select>` has no selected logic — deep links land on an arbitrary option.
- **Fix:** read/validate `request.GET.get("session")` (tenant + open) into context as `selected_id`; add
  `{% if s.pk == selected_id %}selected{% endif %}` in the option loop.
- **Status:** [x] fixed — 5.14 I2a (view selected_id) + I2b (template preselect)

### I3 — void verb unreachable

- **Found by:** code-reviewer
- **Problem:** `BarcodeLabel.void()` exists but no URL/view/template exposes it — a label can never leave
  circulation through the UI.
- **Fix:** add POST-only `barcodelabel_void` route (`labels/<int:pk>/void/`) + view mirroring the tag
  lifecycle pattern (try/except ValidationError → messages, audit write, redirect detail); gated Void button
  on detail (+ list row action) shown when `status != 'void'`, admin-gated.
- **Status:** [x] fixed — 5.14 I3a view / I3b+c re-exports / I3d route / I3e detail button / I3f list action

### I4 — `apps/inventory/views/BarcodeRfidIntegration/BarcodeLabels.py:126` print gate

- **Found by:** security-reviewer (Important) + explorer (Minor)
- **Problem:** `barcodelabel_print` POST flips status/stamps printed_at under bare `@login_required` while
  every other label write is admin-gated — members can stamp/re-print indefinitely.
- **Fix:** add `@tenant_admin_required` above `barcodelabel_print` (GET page stays readable? NO — simplest
  consistent posture: gate the whole view; the print page is a write-surface preview).
- **Status:** [x] fixed — fix(inventory): 5.14 I4 tenant_admin_required on barcodelabel_print - members can no longer stamp/re-print labels

### I5 — `apps/inventory/models/BarcodeRfidIntegration/ScanSessions.py` Meta.indexes + ordering

- **Found by:** performance-reviewer (MEDIUM)
- **Problem:** nothing leads `(tenant, scanned_at)` on the fastest-growing table — rolling-24h aggregate
  degrades to a partition scan; `recent_events` orders `-id` which only approximates recency.
- **Fix:** add `Index(fields=["tenant", "scanned_at"]) name inv_scnev_tnt_scan_idx`; switch ScanEvent
  ordering to `["-scanned_at", "-id"]` (append-only ⇒ same result, rides the index). Generate migration
  (claim next free number).
- **Status:** [x] fixed — 5.14 I5a model index+ordering / I5b migration 0019; migrate OK, seed ×2 idempotent

### I6 — `templates/inventory/barcode/barcodelabel/print.html` N×render requests

- **Found by:** performance-reviewer + frontend
- **Problem:** up to 500 identical `<img src=render>` tags — safety rests on browser dedupe; cold-cache
  clients turn one print run into 500 full request+regeneration cycles. Alt texts also identical ×N.
- **Fix:** fetch the SVG once server-side in `barcodelabel_print` GET (reuse the render logic — extract a
  small helper or import the builder from the view module) and pass it once as context; render ONE
  `<img src="data:image/svg+xml,...">`-free layout: simplest = keep the img URL but wrap frames so the img
  appears ONCE outside the loop plus CSS-repeated visual placeholders… CONTRACT DECISION: pass
  `svg_available` bool + keep a single `<img>` in a header card, and the copies loop renders lightweight
  white frames (number + payload text) noting the browser prints N copies of the sheet; differentiate alt
  with `{% if not forloop.first %} copy {{ forloop.counter }}{% endif %}`.
- **Status:** [x] fixed — 5.14 I6a (_build_label_svg helper + svg_available probe) + I6b (single-img header card + text copy frames)

## Minor

### M1 — ok_rate scale — `views/ScanSessions.py` + `console.html:130`
Raw 0–1 fraction rendered as `%`. Pre-scale in view: `round(ratio * 100, 1)` keeping None guard. — **Status:** [x] fixed — fix(inventory): 5.14 M1 pre-scale console ok_rate to percent in view (template already appends % + None guard, unchanged)

### M2 — stale KeyError comment — `views/BarcodeLabels.py:183`
python-barcode 0.16.1 upper-cases Code39 before validating, so lowercase renders fine; comment contradicts behavior. Rewrite comment to state uppercase-normalization; drop `KeyError` ONLY if you verify an out-of-alphabet char can no longer raise it (keep except-tuple conservative otherwise). — **Status:** [x] fixed — fix(inventory): 5.14 M2 rewrite Code39 KeyError comment (verified empirically: checksum map indexes before validate, so KeyError kept)

### M3 — dead form-error blocks — `templates/inventory/barcode/rfidtag/bulkread.html`
References `form.non_field_errors`/`form.epcs.errors` but the view passes no `form`. Remove the blocks (errors flow via messages). — **Status:** [x] fixed — fix(inventory): 5.14 M3 drop dead form-error blocks from bulkread

### M4 — session list Edit pencil unconditional — `scansession/list.html:103`
Wrap in `{% if obj.status == 'open' %}` to match detail gating. — **Status:** [x] fixed — fix(inventory): 5.14 M4 session list Edit pencil only on open sessions

### M5 — console mode badge echoes junk — `console.html:7`
`request.GET.mode|default:"single"|title` renders "Zzz Mode"; derive from the same branch as the toggle buttons (`{% if request.GET.mode == 'batch' %}`). — **Status:** [x] fixed — fix(inventory): 5.14 M5 console mode badge from validated mode var

### M6 — printer affordance on void labels — `barcodelabel/list.html:135`, `detail.html`, `print.html`
Gate Print behind `{% if obj.status != 'void' %}` everywhere (model refuses anyway). — **Status:** [x] fixed — 5.14 M6a list / M6b detail / M6c print page (also member-hidden per I4 gate)

### M7 — literal "None" badge — `scansession/detail.html:104`
Empty resolved_kind hits the else-branch title; guard `{% if ev.resolved_kind %}` else muted "Unresolved". — **Status:** [x] fixed — fix(inventory): 5.14 M7 guard empty resolved_kind on session detail

### M8 — resolver lot determinism — `models/ScanSessions.py` resolve_code
`LotSerial.objects.filter(...).first()` without ordering is nondeterministic for duplicated numbers (uniqueness is tenant+item+number). Add `.order_by("id")` + docstring note. — **Status:** [x] fixed — fix(inventory): 5.14 M8 resolve_code orders every master lookup by id

### M9 — label target/FK consistency — `forms/BarcodeLabels.py` clean()
`target_type=item` with only `location` set saves with empty derived payload. In `clean()`: when target_type matches exactly one FK field, require that field (item→item, location→location, lot→lot_serial, free→target_ref/pallet_ref) with field errors. — **Status:** [x] fixed — fix(inventory): 5.14 M9 BarcodeLabelForm clean requires target field per target_type

### M10 — payload staleness on retarget edit — `models/BarcodeLabels.py` save()
Editing to point at a different item keeps the stale manually-derived payload. Pragmatic rule: on update, if ANY target field changed AND payload equals the OLD default_payload(), re-derive. Implement carefully; skip with reason if it needs more state than feels safe. — **Status:** [x] fixed — fix(inventory): 5.14 M10 re-derive payload on retarget edit when it still equals the old default

### M11 — seeder verb bypasses — `seed_inventory.py` _seed_rfid_tags/_seed_barcode_labels_and_scans
Tag …0003 spec'd active stays unassigned (no target → refused, swallowed): give it `location=bin_loc` anchor. Tag …0005 force-written lost: activate() then mark_lost() through real verbs. EAN label flipped via `.update(status=...)`: call `ean.print()` instead so printed_at stamps. — **Status:** [x] fixed — 5.14 M11 seeder walks real lifecycle verbs + follow-up (0005 target_ref anchor; verb paths probe-verified)

### M12 — stale urls/__init__ docstring — `apps/inventory/urls/__init__.py:11-17`
Add `labels/`, `sessions/`, `console/`, `tags/` to the documented distinct-first-segments list. — **Status:** [x] fixed — fix(inventory): 5.14 M12 document labels/ sessions/ console/ tags/ in urls package first-segment list

### M13 — render route trailing dot — `urls/BarcodeLabels.py`
`"labels/<int:pk>/render."` looks like a typo (works because {% url %} regenerates verbatim). Rename to `"labels/<int:pk>/render/"`. Url NAME unchanged so templates need no edit. — **Status:** [x] fixed — fix(inventory): 5.14 M13 render route loses stray trailing dot (smoke script's 3 hardcoded URLs updated in gitignored temp/)

### M14 — SVG response CSP header — `views/BarcodeLabels.py` both HttpResponses
Add `Content-Security-Policy: default-src 'none'; style-src 'unsafe-inline'` header (defense-in-depth against future writer-version escaping regressions). — **Status:** [x] fixed — fix(inventory): 5.14 M14 Content-Security-Policy default-src 'none' on both SVG render responses

### M15 — console resolve fan-out — `views/ScanSessions.py` POST
~4 iexact lookups ×300 codes inside one atomic block. Batch-resolve: collect codes list; 4 grouped queries (`sku__in`, `code__in`, `number__in`, `epc__in`) building dicts, then per-code dict lookup + record(). Preserve exact resolver precedence (item beats location beats lot beats rfid) when a code matches multiple masters. — **Status:** [x] fixed — 5.14 M15a resolve_codes helper (+repair commit) / M15b console POST uses it

### M16 — print page frame count clamp — `views/BarcodeLabels.py` print GET
Model caps copies ≤500 but a 500-frame loop is absurd UI; clamp displayed frames to first 50 with a note ("printing N copies — showing first 50 previews"). Pairs with I6. — **Status:** [x] fixed — 5.14 M16a view clamp PRINT_PREVIEW_CAP / M16b template note

## Notes — app-wide / pre-existing (NOT in the fix queue)

- core.utils.next_number read-increment is not concurrency-atomic — documented app-wide limitation.
- crud_list unanchored icontains search across related tables is house-standard.
- Superuser (tenant=None) sees empty registers platform-wide by design.
- Sibling-session MultiLocationManagement files are out of scope and were ignored by all lanes.

## Done well

- **security-reviewer:** textbook tenant discipline end-to-end — every lookup carries tenant=request.tenant including degrade-gracefully paths; caps fire before transactions; the library-escaping decision is documented at the exact line future devs would break it.
- **performance-reviewer:** zero N+1 by construction — resolution snapshots (resolved_label) eliminate per-row hops; KPI strips grouped; bulk_read is two queries total.
- **explorer:** migration provably in sync (makemigrations --check clean); all 24 url names resolve; re-export chains complete.
- **qa-smoke-tester:** reproduced the C1 500 with a minimal probe and cleaned every marked row afterwards.
