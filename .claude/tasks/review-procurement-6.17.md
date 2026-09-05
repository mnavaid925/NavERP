# Review findings — procurement 6.17 Risk & Compliance Management

**Scope:** explicit paths, NOT `BASE...HEAD`. Four concurrent sessions commit to `main` in this one
tree, so a commit range contains 6.16's, 6.18's and 6.19's work; a reviewer handed one files
findings against the wrong sub-module. Every reviewer was scoped to:

```
apps/procurement/{models,forms,views,urls}/RiskComplianceManagement/**   (30 .py)
templates/procurement/riskcompliance/**                                  (26 .html)
apps/procurement/migrations/0028_*.py
+ the 6.17 blocks ONLY of: models/forms/views/urls __init__.py, admin.py,
  views/_helpers.py, seed_procurement.py, apps/core/navigation.py
```

**Already fixed before review, not re-reported:** `_policy_qs` paginating unordered because
`annotate()` drops `Meta.ordering` (commit `d046eaee`).

**Status legend:** `[ ] open` · `[x] fixed` · `[~] skipped — reason`

---

## Pass 1 — code-reviewer (correctness)

### [x] C1 — FIXED — a hit can be deleted out of a *decided* screening, erasing the match the decision rests on
`apps/procurement/views/RiskComplianceManagement/ScreeningHits.py:229`

`screeninghit_delete` has **no status guard at all**. `ComplianceScreening.block()`
(`models/.../Screenings.py:398`) refuses only on `status not in OPEN_STATUSES` — it does not
require hits to be disposed — so a `blocked` screening routinely still carries `open` hits. And
`templates/.../screening/detail.html:217-222` renders Edit + Delete for any `hit.is_open`
**regardless of `obj.is_terminal`**.

**Failure scenario:** block SCR-00005 on a confirmed BIS denied-persons match while its second
alias hit is still open → any logged-in tenant member clicks the bin on that row → the hit is
gone, `recount_hits()` reports 0, and the blocked screening now shows no match at all.

`screeninghit_create` refuses exactly this parent state (`ScreeningHits.py:201-208`) and
`screening_edit`/`screening_delete` refuse a terminal screening (`Screenings.py:285-304`) — the
hit delete route is the only hole. **Fix:** refuse when `obj.screening.is_terminal`, and mirror it
in `screeninghit_edit:216`, which today checks only `obj.is_open`.

**[x] fixed** — `fix(procurement): refuse hit amend/delete once the screening is decided`
(+ 3 template commits). Added `_refuse_if_parent_decided()` and called it from `screeninghit_delete`
and `screeninghit_edit`; gated the controls in `screening/detail.html`, `screeninghit/list.html` and
`screeninghit/detail.html` on `not <parent>.is_terminal`. **Adjudication deliberately NOT gated** —
disposing an open hit under a decided screening adds reasoning, it does not erase evidence.
Proven by `temp/fix617_c1.py` (10/10, rolled back): as both a tenant admin and an ordinary member,
POST delete and POST edit on an open hit under a `blocked` screening leave the **row unchanged**
(`matched_name` intact, `open_hit_count=1 hit_count=2`); an OPEN screening's hit is still deletable.

### [x] I1 — FIXED — `screeninghit_delete` is the one delete verb with no admin gate, and it is the one that unlocks Clear
`apps/procurement/views/RiskComplianceManagement/ScreeningHits.py:227`

All four sibling deletes are `@tenant_admin_required` (`Screenings.py:295`, `RiskSignals.py:290`,
`FraudAlerts.py:334`, `Attestations.py:329`). `clear()` refuses while any hit is `open`.

**Failure scenario:** a non-admin analyst deletes the two open OFAC-SDN hits on SCR-00003; the
admin then opens a clean-looking screening, is offered the Clear button, and clears the supplier —
with nothing on the record showing a 93% SDN match was ever returned. Capture is analyst work;
destroying the match is not. **Fix:** add `@tenant_admin_required`, and hide the delete control
from non-admins in the two list templates (as `screening_delete` already does).

**[x] fixed** — `security(procurement): admin-gate screeninghit_delete like its four siblings`
(+ 3 template commits: `screeninghit/list.html`, `screening/detail.html` and the hit detail's
Danger zone, which is the same control on a third surface). Capture and amend stay ungated —
filing a match is analyst work. Proven by `temp/fix617_i1.py` (8/8, rolled back): a non-admin
member's POST returns **403** with the **row and the `open_hit_count` unchanged**, `clear()` still
refused while the match stands; an admin can still delete and a member can still capture.

### [x] I2 — FIXED (with I11) — `ALERT_KIND = "risk"` is not in `ProcurementAlert.KIND_CHOICES`
`apps/procurement/models/RiskComplianceManagement/RiskSignals.py:207`

The model's own docstring (lines 199-206) promised an `AlterField` at Integrate; it never landed,
and migration `0028` contains none. `DashboardPortal/ProcurementAlerts.py:29-35` still lists only
deadline/approval/delivery/task/contract.

**Failure scenario (two, both reachable by capturing an FHR 70→40 deterioration):** (a) 6.1's kind
filter builds its `<select>` from `KIND_CHOICES`, so Risk is never offered, and a hand-typed
`?kind=risk` is *silently skipped* by `crud_list._enum_values` (`apps/core/crud.py:156-158`),
returning the **unfiltered** inbox; (b) `ProcurementAlertForm.Meta.fields` includes `kind`, so
opening a risk alert at `procurement:alert_edit` renders a `<select>` with nothing selected, and
saving posts the first option — silently re-labelling the alert "Deadline".
**Fix:** add `("risk", "Risk")` to `KIND_CHOICES` + a `kind_css` entry + an `AlterField` migration
(precedent: `0012_alter_procurementalert_kind`).

**[x] fixed (I2 + I11 are one fix)** —
`fix(procurement): register kind=risk on ProcurementAlert, the kind 6.17 raises`
+ `docs(procurement): close the ALERT_KIND hand-off note now that risk is registered`.
`("risk", "Risk")` added to `KIND_CHOICES`, `kind_css["risk"] = "badge-red"`, and the stale
hand-off comment in `RiskSignals.py` rewritten. **MIGRATION OUTSTANDING** — the `AlterField` on
`procurementalert.kind` was deliberately NOT generated here (cross-session announce protocol);
see the OUTSTANDING MIGRATION section at the foot of this file. `manage.py check` is clean
without it. Proven by `temp/fix617_i2.py` (10/10, rolled back): `?kind=risk` finds the risk alert
and **excludes** a non-risk one (so no longer the unfiltered inbox), the kind `<select>` offers
Risk, `get_kind_display()` returns "Risk", and a `ProcurementAlertForm` round-trip keeps
`kind="risk"` instead of silently re-kinding it.

### [x] M1 — FIXED — the fraud board's freshest ageing bucket excludes future-dated alerts
`apps/procurement/views/RiskComplianceManagement/FraudScan.py:274` — the comment claims the bucket
catches anything "dated today or (defensively) later"; the condition is `document_date__lte=today`
(line 270), so a future-dated open alert falls into no bucket and the board's counts sum to less
than `stats.open`. Reachable: `FraudScanForm` bounds `end` only relative to `start`. Fix: drop the
`__lte` bound on the `fresh` bucket.
**[x] fixed** — `fix(procurement): let the freshest ageing bucket catch a future-dated alert`. The
lower bound is omitted when `low == 0`. Verified on seeded acme in a rolled-back transaction: with
one open alert moved to `today+5`, buckets sum **10 = stats.open 10** (it lands in `fresh`); the
pre-fix sum would have been 9.

### [x] M2 — FIXED — `screening_unresolved` evidence text misdescribes a `true_match`
`apps/procurement/models/RiskComplianceManagement/FraudAlerts.py:1221` — the sentence says the
screening "still carries a match nobody has adjudicated", but `_UNRESOLVED_DISPOSITIONS`
(line 211) includes `true_match`, which *has* been adjudicated. On an accusation naming a supplier,
that sentence is the one a reader quotes back. Fix: branch the wording on the disposition.
**[x] fixed** — `fix(procurement): stop calling a confirmed sanctions match unadjudicated`. The
sentence branches on a `has_true_match` annotation that rides the **same** query
(`Max(Case(When(...)))` over the already-filtered hits join, replacing the `.distinct()` that was
doing the same dedupe) — **no extra query**. The rule itself is unchanged. Verified in a
rolled-back 300-day scan: SCR-00003 (open) → "nobody has adjudicated"; SCR-00005 (true_match) →
"somebody confirmed as a true match".

### [~] M3 — Minor — the six names appended to `PROCUREMENT_CONTENT_MODELS` are a no-op
`apps/procurement/views/_helpers.py:41-50` — the tuple is consulted only on the
`content_type__app_label="scm"` branch (lines 70-72); all six 6.17 models are
`app_label="procurement"` and are already matched unconditionally by the first `Q`. **Nothing is
broken** — the rows do reach the feed — but the comment reads as if the edit made them appear.
**App-wide pattern** (`procurementalert`/`eauction`/`rfxevent` above it have the same shape), so
flag rather than fork (L18/L28).

### [x] M4 — FIXED — `fraud_scan` is the only non-PRG POST in 6.17
`apps/procurement/views/RiskComplianceManagement/FraudScan.py:128-168` — re-renders on a
successful POST, so a browser refresh re-runs the scan. Benign (idempotent; a second pass raises 0
and writes no audit row), but `policy_overdue_board`, `policy_raise_attestations`,
`auditseal_create` and `auditseal_verify` all redirect. Fix: pop-once session key + redirect.
**[x] fixed** — `fix(procurement): make fraud_scan a POST/redirect/GET like every sibling verb`.
Pop-once session key carries `results` + both diagnostics lists + the scanned window and rule
selection across the redirect, so the form still describes the numbers beside it. Verified in a
rolled-back transaction: POST → **302**, redirected GET **200 with the results**, second GET 200
with the results block **gone** and the alert count unchanged (12 → 12 → 12, not re-run).

### [x] M5 — FIXED — two create forms have no L39 dead-end notice
`Screenings.py:240` and `RiskSignals.py:218` — in a workspace with no supplier `Party`, the
required `party` field renders as an empty `<select>` on an unsubmittable form.
`templates/.../attestation/form.html:56-64` handles the identical precondition correctly; copy it.
**[x] fixed** — `fix(procurement): add the L39 dead-end notice to the screening form` +
`… to the risk signal form`. Copied the attestation pattern, worded per entity, linking to
`core:party_list`. Verified **both directions**: with suppliers present the notice does not
render; with an empty `party` queryset it does.

### [x] M6 — FIXED — the hit detail page instructs the user toward a control it never renders
`templates/procurement/riskcompliance/screeninghit/detail.html:131` says "If it was captured
wrongly, delete it and record it again" for an adjudicated hit, while the Delete card at line 136
is gated `{% if obj.is_open %}`. The view currently allows it (see C1) — pick one answer across
view, template copy and template gate.
**[x] fixed** — `fix(procurement): make the hit page's delete copy and delete gate agree`. Picked
**the view's** answer, which is also the module docstring's: `screeninghit_delete` has no
`is_open` guard on purpose because delete-and-recapture is the stated correction. The Danger zone
now renders for an adjudicated hit too, under exactly the conditions the view enforces after
C1/I1 (parent open + admin), and the remedy sentence branches three ways so it only ever names a
control that is on the page. Verified on all three states.

### [x] M7 — FIXED — `BATCH_PARTY_LIMIT` is dead code
`apps/procurement/models/RiskComplianceManagement/Screenings.py:163,197` — referenced only from a
URL-module docstring, because `screening_batch` was deliberately cut. Drop the constant with the
feature.
**[x] fixed** — `refactor(procurement): drop BATCH_PARTY_LIMIT with the feature it capped` +
`docs(procurement): note that BATCH_PARTY_LIMIT went with screening_batch`. Removed from module
scope and from the class re-exposure block; the URL docstring now records that the cap went with
the route. `grep` confirms no remaining reference in any `.py`.

### [x] M8 — FIXED — `form-input` on a `<textarea>`
`templates/procurement/riskcompliance/attestation/detail.html:127,136` — every other textarea in
the sub-module uses `form-textarea`; theme.css defines both.
**[x] fixed** — `style(procurement): use form-textarea on the two attestation textareas`.
`.form-textarea` is what carries `min-height: 96px` and `resize: vertical` (theme.css:317).
Zero `<textarea class="form-input">` left in `templates/procurement/riskcompliance/`.

### Noted as done well (no action)
`AuditTrail.py:152-163` — `_need_tenant` **refuses** a tenant-less user on every audit view rather
than following the house "renders empty" convention, because `core.AuditLog.tenant` is nullable and
`filter(tenant=None)` would return every unattributed audit row in the installation. A genuine
cross-workspace read avoided on the page where it would matter most, with the reasoning written
beside the guard. Same care in `attestation_sign` being owner-only at both view
(`Attestations.py:376`) and model (`Policies.py:386`), and in `clear()` asking the database rather
than the cached counter.

### Routed to later passes
- **performance:** `RiskSignals.py:380-385` loads every `SupplierRiskSignal` in the workspace into
  Python on each `risksignal_refresh_board` render; `Screenings.py:428-431` does the same for every
  cleared screening on `screening_rescreen_board` — both uncapped, in a module that otherwise caps
  everything (`SCAN_ROW_LIMIT`, `ROSTER_ROW_CAP`, `BOARD_ROW_CAP`, `MAX_SEAL_ROWS`,
  `CHAIN_WALK_LIMIT`).
- **security:** confirm `auditseal_verify` being non-admin (`AuditTrail.py:613-614`) is acceptable —
  any tenant member can flip another user's `last_verify_ok`/`last_verify_detail` stamps on a seal.
- **frontend:** M5, M6, M8.

---

## Pass 2 — security-reviewer

**Critical: none.** No cross-tenant read or write path exists. Verified rather than assumed: every
`get_object_or_404` carries `tenant=request.tenant` (or `screening__tenant=` for the tenant-less
`ScreeningHit`); no pk-only fetch anywhere; the `AuditLog.tenant IS NULL` trap is handled by
refusing a tenant-less user outright rather than filtering `tenant=None`; no `|safe`, `mark_safe`,
`autoescape off`, `.raw()`, `.extra()`, `cursor.execute` or `@csrf_exempt` in 30 `.py` + 26 `.html`;
every `method="post"` form has `{% csrf_token %}`; every `confirm()` interpolates only a
system-assigned number and contains no apostrophe (L42 respected); `audit_trail_export` passes every
cell **and header** through the shared `csv_safe`, including the `changes` JSON.

### [x] I3 — FIXED — ungated `policyattestation_edit` defeats the admin-gated withdrawal
`apps/procurement/views/RiskComplianceManagement/Attestations.py:311-325`
(+ `forms/.../Policies.py:87`, `templates/.../attestation/detail.html:165-178`)

`policyattestation_edit` is `@login_required` only, while `policyattestation_delete` (`:328-344`)
and `attestation_exempt` (`:401-455`) are `@tenant_admin_required` — and the form exposes
`["policy", "user", "due_on"]`, not merely the deadline its docstring and button label ("Change the
deadline") claim. The template hides the button behind `{% if is_admin %}` under an
"Administration" heading, so the restriction is **cosmetic**: the route has no gate.

**Exploit:** Mallory, an ordinary member, owes `PPOL-00003` (attestation pk 41), overdue and on the
chase board.
```
POST /procurement/policy-attestations/41/edit/
csrfmiddlewaretoken=<from any 6.17 page>&policy=7&user=41&due_on=2099-01-01
```
`crud_edit` resolves pk 41 with `tenant=request.tenant` (same tenant → passes), `_reject_foreign`
passes (same-workspace user), `clean_policy` passes (still published). Her row leaves
`policy_overdue_board` and the `stats.overdue` tile permanently. Substituting `user=<Bob's pk>`
transfers the obligation wholesale — her name leaves the roster, Bob is chased for it, and she has
achieved the withdrawal `policyattestation_delete` exists to restrict to admins. Works on **any**
pending row in the workspace, not just her own.

6.17-specific, not the app-wide CRUD pattern: no sibling entity here has an admin-gated delete whose
effect an ungated edit reproduces. **Fix:** add `@tenant_admin_required` to the route, AND set
`self.fields["policy"].disabled = True` / `["user"].disabled = True` when `self.instance.pk` —
`disabled` makes Django ignore the POSTed value entirely, so a crafted POST cannot reach it either.

**[x] fixed** — `security(procurement): admin-gate policyattestation_edit` +
`security(procurement): freeze policy and user on an existing attestation`. Both halves applied as
written. Proven by `temp/fix617_i3.py` (12/12, rolled back) against the reviewer's exact exploit:
Mallory POSTs `policy=<other>&user=<Bob>&due_on=2099-01-01` on her own overdue row → **403**, and
`due_on`, `user` and `policy` are all **unchanged** with the row still on the overdue set. An
admin's identical POST changes **only** `due_on` — the disabled fields ignore the payload even for
a privileged caller. Create is untouched (fields not disabled without `instance.pk`).

### [x] M9 — FIXED — `matched_on` writes an employee's street address verbatim
`apps/procurement/models/RiskComplianceManagement/FraudAlerts.py:854` → `:1055`

Answering the routed question: masking **does** hold in `scan()` for `tax_id` (`_mask_tail` →
`••••1234`) and `contact` (`_mask_contact` → `a••@acme.test`), but **not** for `address` — line 854
builds `shown = f"{line1}, {city}"` verbatim and `_emit_pairs` carries it into `_matched_on`. For
`vendor_employee_match` that value is by definition the employee's home address; it renders on
`fraudalert/list.html` and `detail.html` (both `@login_required`, not admin-gated) and is searchable
via `search_fields`. The seeder's hand-raised row masks, which is why fixtures look clean.

**Calibrated honestly:** the same audience can already read `core.Address` at `core:address_list`,
so this is not a new audience — it is a break of the module's own stated invariant (*"enough of the
value to recognise it and not enough to leak it"*, lines 226-227), and a home address pinned next to
a named employee inside an accusation record. **Fix:** `shown = city or _mask_tail(line1)`.
**[x] fixed** — `security(procurement): mask the address written into matched_on`. Applied exactly
as prescribed. The comparison **key** is untouched, so the match still works on the full
normalised address; only the stored/displayed value changes. Verified with a synthetic
vendor/employee pair sharing `17 Ashgrove Terrace, Bristol` inside a rolled-back scan:
`matched_on == "address Bristol"` — street line absent, still recognisable.

### [x] M10 — FIXED (half; other half superseded by M14) — seal detail/verify are cheap, uncapped amplifications for the lowest-privilege user
`apps/procurement/views/RiskComplianceManagement/AuditTrail.py:560-569`, `:613-639`

`auditseal_verify` re-reads up to `MAX_SEAL_ROWS + 1` = 50,001 `AuditLog` rows and SHA-256s each per
POST, unthrottled. `auditseal_detail` is worse in one respect: it fetches the seal **without**
`.defer("row_fingerprints")` (unlike `auditseal_list:396`), so every **GET** parses a JSON column of
up to 50,000 pairs — and a GET is triggerable cross-site from a page a logged-in user visits, no
CSRF token needed.

Sharper variant: on an **already-broken** seal, verify writes one `AuditLog` row per press
(`:637-638`). An attacker who tampered and was detected can spam the button to bury the
`verification_failed` evidence under thousands of identical rows — inside the very table being
sealed — and inflate every future seal's hashing cost. **Fix:** `.defer("row_fingerprints")` on the
detail read, and audit only the *transition* into failure (`if not ok and was_ok is not False`).
**[x] fixed (the transition half)** — `security(procurement): audit only the DISCOVERY of a broken
seal`. `was_ok` is read from the stamp before re-verifying; the audit row is written only when it
is not already `False`, so a break → repair → break sequence is still reported all three times.
Verified in a rolled-back transaction: intact seal ×3 presses → **0 rows**; first press on a
freshly broken seal → **1 row**; 9 further presses → **0 more rows**, seal still reporting broken.

**The `.defer("row_fingerprints")` half is `[~]` skipped — superseded by M14**, which refutes it:
`auditseal_detail` genuinely needs the ROOT's fingerprint map for `_entries_covered`. M14's
version (defer the PREVIOUS seal's copy) is the correct form and is applied under M14.

### [~] M11 — SKIPPED (needs a migration) — verification stamps have no actor, and a passing verify leaves no record
`apps/procurement/models/RiskComplianceManagement/AuditSeals.py:216-218` (surfaced at
`AuditTrail.py:523-526`) — no `last_verified_by`, and a pass writes no `AuditLog` row, so
`auditseal/detail.html` renders "Last full verification passed on …" with nobody's name on it, on a
route any member can trigger. On an evidence-grade record an auditor cannot tell whether a
responsible person ran the check. **Fix:** one nullable `last_verified_by` FK + pass `user` into
`verify()`.
**[~] skipped — needs a schema migration this session is not permitted to generate.**
The fix was written in full (nullable `SET_NULL` FK on `AuditSeal`, `verify(user=None, stamp=True)`
stamping it through the same targeted `.update()`, `select_related("last_verified_by")` on the
detail read, a nullable-guarded "Checked by" row on `auditseal/detail.html`, and `user=owner` at
the seeder's verify call) and then **reverted**, because unlike I2 (choices-only) and I9 (an index),
an `AddField` changes every `SELECT`: with the column absent from the database, **every** seal page
raised
`OperationalError (1054, "Unknown column 'procurement_auditseal.last_verified_by_id'")`
and the 253-check smoke sweep failed. A fix that turns a green check red is the wrong fix (L38 §3).
**Hand-off:** this one must be done as model + migration **in the same run** by the session that
owns migrations — it cannot be split the way I2 and I9 safely can. Nothing is left half-applied;
`git status` is clean for all four files.

### [x] M12 — FIXED — seals never cover `tenant IS NULL` audit rows
`apps/procurement/models/RiskComplianceManagement/AuditSeals.py:315-317`;
`views/.../ScreeningHits.py:179`, `:233`, `:278`

`seal_now` selects `filter(tenant=tenant, id__gt=last_id)` and `AuditLog.tenant` is nullable, so any
unattributed row falls outside every chain in every workspace — its later modification leaves no
evidence, the exact property the module exists to provide. The docstring's claim that a seal covers
"the tenant's WHOLE audit range by id" is true only for attributed rows.

`auditseal_create` and `fraud_scan` pass `tenant=` explicitly; the four `write_audit_log` calls on
the tenant-**less** `ScreeningHit` do not, falling through to `write_audit_log`'s
`getattr(user, "tenant", None)` fallback. **Not currently reachable as NULL** (`TenantMiddleware`
sets `request.tenant = user.tenant`), but it is the one place in 6.17 whose seal coverage rests on
that coincidence rather than an explicit argument. **Fix:** pass `tenant=screening.tenant`.
**[x] fixed** — `security(procurement): pass tenant explicitly on the ScreeningHit audit writes`.
All four calls now pass `tenant=screening.tenant`. Verified in a rolled-back transaction across
create/edit/dispose/delete: **4 audit rows written, 0 with `tenant` NULL, 4 scoped to acme**.

### [x] M13 — FIXED — operator-typed `matched_on` steers the detector's dedupe key
`apps/procurement/forms/RiskComplianceManagement/FraudAlerts.py:61-63`;
`models/.../FraudAlerts.py:453-461` — `_key_attribute()` derives the key's attribute segment from
`matched_on`'s first word, so a member can hand-raise a pair with `matched_on = "tax_id …"`,
producing exactly the key a later scan would compute. `_upsert` then only refreshes and never
re-opens a disposed alert, so a pre-emptive row disposed `unsubstantiated` means the real detection
can never surface as open. Not a privilege escalation (an admin could dispose it anyway); the
difference is the finding is never *visible* as open to anyone else. **Fix:** `_key_attribute()`
returns `"manual"` for hand-raised rows so they can never collide with the detector's key.
**[x] fixed** — `security(procurement): stop a typed matched_on steering the detector's key`.
`_key_attribute()` now always returns `"manual"`, which is what its own docstring already claimed.
Proven in a rolled-back transaction: hand-raised key `vem:1156:1157:manual` vs the detector's
`vem:1156:1157:address` — **no collision** — and after disposing the hand-raised row
`unsubstantiated`, the scan still raises its own **open** alert for the pair.

### VERDICT on the routed question — `auditseal_verify` un-gated is ACCEPTABLE, keep it
The framing "any member can flip another user's stamps" does not hold on this code:
1. **The stamps cannot be flipped to a false value.** `verify()` recomputes from live data every
   time. A member cannot make a broken seal read green or an intact seal read red — whatever they
   write is the truth about the range at that instant. Materially unlike a `status` column a POST
   sets to a chosen value.
2. **There is no "another user's" stamp to overwrite.** The columns carry no actor (M11) — they are
   the cached result of the last machine check, not a per-user assertion.

The docstring's design argument also holds: verification is read-mostly, and *a tamper check only an
administrator can run is a check nobody runs*. Gating it would leave `last_verify_ok = None` on most
seals. The real costs are M10 and M11; fixing those is what makes the un-gated design fully
defensible. **The gate is not the problem.**

### Explicitly NOT reported (app-wide, do not fork in 6.17)
`fraudalert_create`/`_edit`, `screening_edit`, `risksignal_edit` being `@login_required` only is the
app-wide CRUD gate across all 13 modules; `_changed(form)` recording only the post-change value with
no before-image is app-wide `apps/core/crud.py` behaviour. Checked and correct as written:
`attestation_sign`'s **double** owner check (view `Attestations.py:376` and model
`Policies.py:385-387`, correctly refusing tenant admins *and* superusers), both suspension links
verifying the counterparty rather than only the tenant, the seeder's exclusive use of verb methods,
and `editable=False` on every derived column in migration 0028.

---

## Pass 3 — performance-reviewer

Backend is **MySQL** — no `DISTINCT ON`.

### [x] C2 — FIXED — `auditseal_list` drags the *previous* seal's 50k-pair JSON blob on every page
`apps/procurement/views/RiskComplianceManagement/AuditTrail.py:396`

`defer()` scopes to the **root model only**. `select_related("prev_seal")` is an unrestricted
self-join pulling the previous seal's full row **including its `row_fingerprints` JSONField**, which
the `defer("row_fingerprints")` beside it does not touch. And `auditseal/list.html` **never renders
`obj.prev_seal` at all** (its only occurrence, line 44, is a comment).

**Cost:** 15 rows/page × up to `MAX_SEAL_ROWS` = 50,000 `[id, 16-hex]` pairs per blob ≈ 1.4 MB per
seal → **up to ~21 MB fetched and JSON-decoded per page render**, for a column nothing on that page
reads. Query count unaffected (still 2) — this is pure payload, which is why no
`assert_max_num_queries` can catch it.
**Fix:** drop `"prev_seal"` from the list `select_related` entirely.

**[x] fixed** — `perf(procurement): drop the unused prev_seal join from auditseal_list`.
Before/after measured at SQL level (`temp/fix617_c2.py`): the page query named `row_fingerprints`
**1x before** (the joined `prev_seal` alias — the root was already deferred) and **0x after**.
Query count unchanged at 2. Worst case at `MAX_SEAL_ROWS`: ~1.4 MB/seal x 15 rows =
**~21 MB/page → 0**.

### [x] I4 — FIXED — `risksignal_refresh_board` loads every signal in the workspace (CONFIRMED)
`RiskSignals.py:380-385` — `filter(tenant=…).select_related("party")`, **no slice, no `.only()`, no
`.iterator()`**, iterated in a `for` loop so `_result_cache` keeps every row resident.
**Not an N+1 — an unbounded row load.** At 5,000 signals: 5,000 instances (22 columns incl. the
`notes`/`review_note` TextFields) **plus** 5,000 joined `core.Party`. With ~200 suppliers × ~3
metrics ≈ 600 distinct series, **~88% of fetched rows are discarded by the next `setdefault()`**.
The only uncapped read in a module that caps everything else.
**Fix:** the view already builds `parties`/`party_ids` — index them by pk, push
`party_id__in=party_ids` into SQL, drop the join, add `.only(...)` (9 columns) and
`.iterator(chunk_size=2000)`, then read `parties_by_id[signal.party_id]` at line 409.

**[x] fixed** — `perf(procurement): stop loading every risk signal to build the refresh board`.
Applied exactly as prescribed. **Before/after** (`temp/fix617_i4i5.py`): columns per row
**27 → 8** (drops the `notes`/`review_note` TextFields), joined `core.Party` rows **N → 0** (the
row-dict reads `parties_by_id[signal.party_id]`), rows fetched narrowed to monitored suppliers'
only by `party_id__in` in SQL, and `_result_cache` residency removed via
`.iterator(chunk_size=2000)`. Queries selecting the signal `notes` column: **1 → 0**. Page still
renders 200 with `Refresh overdue` and `Never monitored` present; query count unchanged at 9.

### [x] I5 — FIXED — `screening_rescreen_board` loads every cleared screening (CONFIRMED)
`Screenings.py:428-431` — same shape. At 5,000 cleared screenings: 5,000 instances × 20 columns
incl. two TextFields, ~200 survive `setdefault`. Secondary: `party__in=parties` passes **Party
objects**, so Django inlines every pk into the `IN (…)` SQL text (a 5,000-element IN list —
`max_allowed_packet` exposure). Same `.only()` + `.iterator()` + `party_id__in` fix.

**Refuted sub-point (leave as is):** the missing `select_related("party")` here is **correct**.
`rescreening_due.html` takes `row.party` from the already-fetched `parties` list and never touches
`screening.party`; adding the join would be pure waste.

**[x] fixed** — `perf(procurement): stop loading every cleared screening to build the rescreen
board`. `party__in=parties` (Party OBJECTS, inlined pk-by-pk into the `IN (...)` SQL text) replaced
with `party_id__in=party_ids`; `.only(...)` **26 → 7 columns** (drops `notes`, `decision_note`,
`threshold_rationale`); `.iterator(chunk_size=2000)`. **The refuted sub-point was honoured —
`select_related("party")` was NOT added.** Queries selecting the screening `notes` column:
**1 → 0**. Page still renders 200 with `Never screened` present; query count unchanged at 9.

### [x] I6 — FIXED — `risksignal_list` N+1 on `reviewed_by`
`RiskSignals.py:59` vs `risksignal/list.html:171` — `_ROW_RELATIONS = ("party",)` but the template
renders `obj.reviewed_by`. **+1 query per reviewed row**: a mature 15-row page goes from ~7 to ~22
queries. The module docstring at line 23 reasons about exactly this for `party` and then does not
extend it. **Fix:** `_ROW_RELATIONS = ("party", "reviewed_by")`; drop the now-duplicate from
`_DETAIL_RELATIONS`.

**[x] fixed** — `perf(procurement): join reviewed_by on the risk signal register`. Applied as
prescribed, plus the module docstring's query-shape paragraph updated so it still describes the
code. **Before/after** (`temp/fix617_nplus1.py`, every row forced `reviewed` inside a rolled-back
transaction): row-loop queries **6 → 0** on a 6-row page; **+15 → +0** at a full page.

### [x] I7 — FIXED — `fraudalert_list` N+1 on `resolved_by`
`FraudAlerts.py:55` vs `fraudalert/list.html:188` — identical shape; `resolved_by` is in
`_DETAIL_RELATIONS` but not the row set. **+1 query per terminal row**, up to +15 on a settled
register.

**[x] fixed** — `perf(procurement): join resolved_by on the fraud alert register`. **Before/after**
(`temp/fix617_nplus1.py`, every row forced resolved): row-loop queries **12 → 0** on a 12-row
page.

### [x] I8 — FIXED — `_screening_options` is an uncapped dropdown over an append-only ledger
`ScreeningHits.py:101` — the parent-screening filter `<select>` returns **every**
`ComplianceScreening` in the workspace. This **forks** the app-wide pattern rather than following
it: *party* dropdowns are uncapped app-wide (bounded master — correct, leave alone), but
*transactional/ledger* dropdowns are capped app-wide —
`GoodsReceiptInspection/ReceiptBoards.py:163` and `ReturnsToVendor.py:77` both use `[:200]`.
Screenings grow forever. At 5,000: 5,000 instances + 5,000 joined parties + 5,000 `<option>`
elements per hit-queue render. **Fix:** append `[:200]` and note the cap in the docstring.

**[x] fixed** — `perf(procurement): cap the hit queue's parent-screening dropdown at 200`. Added
`FILTER_OPTION_CAP = 200` beside the other module caps and documented why a ledger dropdown is
capped where a party dropdown is not. **Verified the slice compiles to SQL `LIMIT`** (so the cost
is bounded before rows are materialized), the queue still renders 200 with its `All screenings`
option, and `?screening=<pk>` still narrows correctly — the filter runs against the queryset, not
this list, so an off-list screening is still reachable.

### [x] I9 — FIXED — `SupplierRiskSignal` is missing its `(tenant, ordering)` index
`RiskSignals.py:362-373` — `Meta.ordering = ["-observed_on", "-id"]` drives every unfiltered page,
but `prc_srs_series_idx` and `prc_srs_tnt_party_obs_idx` both put `party` **between** `tenant` and
`observed_on`, so MySQL can use neither for `WHERE tenant_id=? ORDER BY observed_on DESC` — page 1
is a **full filesort over every signal in the workspace**. It is the only one of the five 6.17
models missing this (`ComplianceScreening` ✓, `FraudAlert` ✓, `PolicyAttestation` ✓, `AuditSeal` ✓).
**Fix:** `models.Index(fields=["tenant", "-observed_on"], name="prc_srs_tnt_obs_idx")` + migration.

**[x] fixed** — `perf(procurement): index SupplierRiskSignal on (tenant, observed_on)`. Added as
**ascending** rather than `-observed_on`: that is the shape all four sibling 6.17 models use, and
the backend is **MariaDB 10.4**, which parses `DESC` in an index definition only to ignore it and
scans an ascending index backwards anyway; InnoDB's implicit PK suffix is what satisfies the `-id`
tie-break. **Proven with `EXPLAIN` on the real table**: before →
`key=prc_srs_tnt_party_obs_idx, Extra="Using where; Using index; Using filesort"`; with the index
present → `Extra="Using where; Using index"` — **filesort gone**. Probed under a throwaway index
name and dropped again so it cannot collide with the migration. **MIGRATION OUTSTANDING** — see
the section at the foot of this file.

### [x] M14 — FIXED — `auditseal_detail`: the security pass's flag is half right
`AuditTrail.py:560-562`. **Refuted:** the page genuinely needs the root's `row_fingerprints` —
`_entries_covered` calls `seal.fingerprint_map` to mark entries and reconstruct `missing` ids;
deferring it would trade a column read for a lazy re-fetch and be strictly worse. **Confirmed
(different column):** `select_related("prev_seal")` again pulls the *previous* seal's
`row_fingerprints` while the page needs only `prev_seal.number`/`.pk`/`.chain_digest` — ~1.4 MB of
dead payload. **Fix:** `.defer("prev_seal__row_fingerprints")`.
**[x] fixed** — `perf(procurement): defer the PREVIOUS seal's fingerprint blob on seal detail`.
The refutation was honoured: the root's column is **not** deferred. **Before/after**
(`temp/fix617_c2.py`): the detail query named `row_fingerprints` **2× before** (root + prev) and
**1× after** (root only). Page still renders 200 with the entry range, both digests and the marked
covered-entry sample.

### [x] M15 — FIXED — three dead-weight indexes and one missing hot one
- `FraudAlerts.py:371` — `document_date = DateField(db_index=True)` creates a **standalone** index
  in addition to `prc_frd_tnt_docdate_idx` on `(tenant, document_date)`. Every query here is
  tenant-scoped, so nothing can ever lead on bare `document_date`. Dead weight on the write path of
  the fastest-growing, append-only table (`scan()` bulk-upserts into it). Drop `db_index=True`.
- `AuditSeals.py:225` — `prc_asl_tnt_sealed_idx` on `(tenant, sealed_at)`: nothing filters or orders
  by `sealed_at`. Low-volume table, flagged for completeness.
- `Policies.py:312` — `prc_patt_tnt_policy_idx` on `(tenant, policy)` is a strict prefix of
  `unique_together ("tenant","policy","user")`, which MySQL already backs with a unique index.
- **Missing:** `fraudalert_list` offers five filters; four have a `(tenant, col)` index,
  `assigned_to` does not. Add `prc_frd_tnt_assignee_idx` in the same migration.
**[x] fixed — all four parts, each verified against the LIVE schema before touching it**
(`SHOW INDEX`): `procurement_fraudalert_document_date_9599b9da` existed alongside
`prc_frd_tnt_docdate_idx`; `prc_asl_tnt_sealed_idx` existed with `sealed_at` appearing only in
`admin.list_display`, one dict literal and three template render sites (never a filter or an
order_by); `prc_patt_tnt_policy_idx (tenant_id, policy_id)` is a strict prefix of
`..._uniq (tenant_id, policy_id, user_id)`; and `assigned_to` **is** the fifth `fraudalert_list`
filter with only a bare FK index. Three commits:
`perf(procurement): fix FraudAlert's index set - drop one dead, add one hot`,
`… drop AuditSeal's unused (tenant, sealed_at) index`,
`… drop the PolicyAttestation index the unique key already covers`.
**MIGRATION OUTSTANDING** (index-only — nothing breaks before it runs).

### [x] M16 — FIXED (`.only()` half; `.iterator()` correctly NOT applied) — `seal_now`/`verify` materialize full `AuditLog` instances
`AuditSeals.py:315-317`, `371-374` — `canonical_line` reads 8 columns but `list(...)` pulls full
instances, up to 50,000. `.only(...)` would cut row width with zero behaviour change.
**The cap itself is correct and confirmed:** `[:MAX_SEAL_ROWS]` compiles to SQL `LIMIT`, so
discovering you are over the cap costs the same on a 10-row backlog as a 10-million-row one — L40 §1
satisfied. **`.iterator()` is NOT applicable and must not be suggested:** `seal_now` needs
`rows[0]`/`rows[-1]`/`len(rows)`, `verify` needs `len()` and random access `rows[position]`.
**[x] fixed — the `.only(...)` half only.** `perf(procurement): narrow seal_now and verify to the
eight hashed columns`. **`.iterator()` was NOT applied**, exactly as the finding instructs.
Because `canonical_line` is PINNED, byte-identity was **verified rather than assumed**:
`canonical_line` over 200 real rows produced **0 mismatches** between full and `.only()`-narrowed
instances, `compute_digest` returned the **same hash** from both, and the seeded **ASL-00001
(3,716 rows, #1–#6383) still verifies True** against its stored digest.

### [x] M17 — FIXED — `attestation_list` N+1 on `exempted_by`
`Attestations.py:76` vs `attestation/list.html:143` — same shape as I6/I7; Minor only because
exemptions are rare.
**[x] fixed** — `perf(procurement): join exempted_by on the attestation register`. Measured with
every row forced exempted inside a rolled-back transaction: row-loop queries **2 → 0**.

### [x] M18 — FIXED — seeder block 2 is the only one not wrapped in `transaction.atomic()`
`seed_procurement.py:4222-4260`. **No `bulk_create` finding:** `TenantNumbered.save()` mints the
number and `derive()` stamps seven columns from the *preceding* row, so per-row `.save()` is correct
and `bulk_create` would break both.
**[x] fixed** — `fix(procurement): wrap 6.17 seeder block 2 in transaction.atomic`. The refusal to
`bulk_create` is now written into the code as a comment so it is not re-raised. This block matters
more than the others: a half-written series leaves later rows derived against a predecessor that
never landed, and the block's own existence check would then **skip the repair** on the next run.
Verified by deleting acme's six signals inside a rolled-back transaction and re-running the seeder:
**6 rows recreated**, `derive()` chain intact (`82.00 → new`, `71.00 → deteriorated from 82.00`),
inversion check still correct. Re-running with data present is still a clean skip.

### Verified correct — explicitly refuted, do not "fix"
- **`FraudAlert.scan()` is well built.** `_scan_context` issues a bounded **≤8 queries regardless of
  row count**; every source list carries a `[:SCAN_ROW_LIMIT]` slice compiling to SQL `LIMIT`, so
  the cap is enforced **before** rows are materialized. `MAX_SCAN_WINDOW_DAYS` is checked
  arithmetically before any query. All six `_detect_*` read only from `ctx` dicts — **zero
  per-candidate queries**. `_existing_by_key` chunks at 1000 keys/`IN`. `_emit_pairs` is O(n²)
  within a group but `MAX_GROUP_SIZE = 25` bounds it at 300 pairs.
- **Pagination total ordering — all eight registers checked, seven refuted.** Every register carries
  a tie-break; `_policy_qs` is the only `annotate()` queryset and already fixed in `d046eaee`. **No
  second instance of the bug.**
- **`count()`/`len()` discipline correct throughout**, including `{{ open_hits|length }}` on an
  already-materialized list (a `.count()` there would be a second round trip).
- **All five `_stats` helpers are one `.aggregate()`** with conditional `Count(filter=Q(...))` — no
  per-status count-per-card. `_by_rule`/`_by_severity` are one grouped `values().annotate()` each;
  `_ageing` is one conditional aggregate for all four buckets.
- **Zero DB work in any of the 26 templates** — no `.count`/`.all` on a related manager inside any
  `{% for %}`. All row-dicts precomputed in the views.
- **All seven detail-page `select_related` sets are complete**; no chained-`__str__` misses.

---

## Pass 4 — frontend-reviewer

**Counts checked** (so a short count reads as a broken glob, not a clean bill): 26/26 templates ·
8 view modules cross-read · **17 live `confirm()` handlers** (32 raw hits − 15 in `{% comment %}`
prose) · **101 `badge-*` tokens** (92 in markup, 9 in comment prose) — **0 non-existent in markup** ·
59 distinct CSS classes, **0 missing from theme.css** · 44 `stat-icon` modifiers, all real ·
56 distinct `{% url %}` names, all resolve · 29 filter selected-state comparisons, all correct ·
22 `get_full_name|default:` uses, all nullable FKs guarded · **8/8 registers use
`partials/pagination.html`** (no hand-rolled paginator) · `|safe` 0, `|slugify` 0, multi-line
`{# #}` 0.

**Critical: none.** No 500 risk, no comment leak, no unstyled badge, no missing context name, no
`NoReverseMatch`, no unguarded pagination. On the two recurring classes specifically: every `{#`
closes on its own line and all 26 files use `{% comment %}` for multi-line headers (L2 clean); the
9 `badge-success`/`badge-warning` grep hits are **all prose inside `{% comment %}` blocks warning
about the lesson** — zero reach live markup (L33 clean).

### [x] I10 — FIXED (latent, worked today) — `{{ act.confirm }}` is HTML-escaped into a JS string literal
`templates/procurement/riskcompliance/attestation/detail.html:123` and `:132`;
`templates/procurement/riskcompliance/policy/detail.html:116`

```django
onsubmit="return confirm('{{ act.confirm }}');"
```
The three strings this resolves to (`Attestations.py:265`, `:281`, `Policies.py:382`) contain no
apostrophe today, so the dialog fires — **not a live bug**. But the escaper is wrong for where the
value lands: autoescape turns `'` into `&#39;`, the HTML parser decodes it back to a bare `'`
*before* the JS engine sees it, the literal terminates, the handler throws, `onsubmit` returns
`undefined`, and **the form submits with no confirmation at all**. The other 14 handlers are
hand-audited literal copy whose apostrophes we control; these three take their copy from Python, one
word away from silently disarming a sign / exempt / raise-roster dialog, with nothing failing.
**Fix:** `{{ act.confirm|escapejs }}` in all three — `escapejs` emits `'`, which the HTML
parser will not decode.

**[x] fixed** — `fix(procurement): escapejs the two Python-authored confirm strings` +
`fix(procurement): escapejs the raise-roster confirm string`. All three handlers now use
`|escapejs`. Verified: an isolated template render of the same expression turns
`You won't` into `&#x27;` under autoescape and into `'` under `escapejs`; both live pages
still return **200 with their confirm handlers present**.

**No stored-XSS vector:** the other 14 handlers interpolate only `number`, which is
`CharField(editable=False)` with a `NUMBER_PREFIX` (`models/_base.py:64`) — system-assigned, cannot
carry a quote. No user-typed field reaches any confirm string.

### [x] M19 — FIXED — unreachable `{% empty %}` branch
`risksignal/detail.html:254-261` — "No series yet" can never render: `series` filters on
`party_id`/`provider`/`metric` equal to `obj`'s own, so it always contains `obj` itself
(`RiskSignals.py:193` says so). Drop the block or reword the card.
**[x] fixed** — `fix(procurement): move the lone-observation note off an unreachable branch`.
Neither option verbatim: the branch is dropped **and** its copy is kept, moved to the state it was
actually written for — `{% if series|length == 1 %}` below the table — with a comment recording why
there must be no empty branch. Verified on both states: the 1-row `ser_rating` series shows the
note, a 2-row `fhr` series does not, and "No series yet" appears nowhere.

### [x] M20 — FIXED — always-true nested guard
`screeninghit/detail.html:83` — `{% if allowed_dispositions %}` sits inside `{% if obj.is_open %}`
(line 79) and the view sets `allowed_dispositions = _TERMINAL_DISPOSITION_CHOICES if obj.is_open
else []`. With no `{% else %}`, a future change to that invariant renders the card with an empty
body. Drop the inner `{% if %}` or give it an `{% else %}`.
**[x] fixed** — `fix(procurement): give the adjudication card's inner guard an else branch`. Kept
the test (it guards the picker's OPTIONS, and a card offering a verb with nothing to choose is
worse than one that says why) and gave it the `{% else %}`, plus a comment recording the invariant.
Verified: an open hit still renders the picker, fallback absent.

### [x] M21 — FIXED — per-row create button carries no row identity
`rescreening_due.html:93`, `risk_refresh_due.html:121` — the `plus` icon in the Actions column links
to bare `screening_create`/`risksignal_create`, identical on every row, while the `history` icon
beside it correctly carries `?party={{ row.party.pk|stringformat:"d" }}`. In an Actions column a
button reads as row-scoped. Either drop it (the page header already has the CTA) or add `?party=…`
and seed `initial` from it in `_screening_form`/`_signal_form`.
**[x] fixed** — the second option, in four commits (two views, two templates).
`_initial_party()` is deliberately strict (L11): `as_db_int` first, then a check against the
**form's own** tenant-scoped, role-narrowed party queryset, and `initial` on the **create path
only** so a URL parameter can never re-point an existing record. Verified **12/12 across both
forms**: a valid party preselects; junk `abc`, an over-range 20-digit value, a nonexistent pk and
a **cross-tenant** pk all render 200 with nothing preselected.

### [~] M22 — Minor — `<dt>`/`<dd>` outside a `<dl>` — APP-WIDE, do not fork
7 places (`fraudalert/detail.html:163`, `risksignal/detail.html:106,123`,
`screening/detail.html:62,80`, `screeninghit/detail.html:56,107`): a bare
`<div class="detail-item">` wrapping `<dt>`/`<dd>` with no enclosing `<dl>`. **Renders correctly** —
theme.css styles them via the descendant selectors `.detail-item dt`/`.detail-item dd`
(`static/css/theme.css:356-357`) — it is only invalid HTML, and it appears 28 more times across 12
templates outside this sub-module. Record, do not fix here (L18/L28).

### Checked and cleared — do NOT "fix" these
- `{% if r.amount is not None %}` / `{% if results is not None %}` / `{% if row.days_late is None %}`
  — Django has no `None` literal, but `smartif`'s `TemplateLiteral.eval` resolves with
  `ignore_failures=True`, so the operand becomes Python `None` and the comparison is **correct**.
  Verified against `django/template/base.py`.
- `screeninghit/list.html:146` delete **not** wrapped in `{% if is_admin %}` is correct *as built* —
  `screeninghit_delete` is `@login_required` only. (Note: I1 changes that view; the template must be
  updated in the same fix, which is why I1 already says so.)
- `attestation/detail.html:50,75`, `attestation/list.html:127`, `policy/detail.html:161`,
  `policy_overdue.html:111` use `obj.user.get_full_name|default:…` unguarded — **safe**:
  `PolicyAttestation.user` is `CASCADE` with no `null=True`.
- Filter controls use `aria-label` rather than a visible `<label for>` — a valid accessible name and
  the app-wide `.filter-bar` pattern. Every `<label for>` inside a form template is correctly paired
  to `{{ field.id_for_label }}`.
- The 7 underscore filenames at the sub-module root are standalone board/report pages, allowed by
  CLAUDE.md rule 6 — none is a banned `<entity>_<page>.html`.
- The two deliberate exceptions (`auditseal/` no form/edit/delete; `policy/` no form) verified as
  intended.

### Structural point worth keeping
The badge architecture is the *right* fix for L33, not merely a correct instance of it. Across 26
templates there is exactly **one** `{% if %}` badge ladder (`audit_trail.html:209`), and it exists
for a defensible reason — `AuditLog` belongs to `core` and 6.17 adds no column to it — with exact
CHOICES values, a `badge-muted` `{% else %}`, and the label always from `get_action_display`. Every
other badge reads a `*_css` value from a `_CSS` map in the model or view, and those maps emit only
the six real classes (78 occurrences in Python, zero semantic names). **A future contributor cannot
reintroduce `badge-success` by editing a template — there is no ladder to edit.** Same discipline on
`state_css` in every row-dict contract.

---

## Pass 5 — explorer (integration seam)

Scoped to the seam — what a reviewer looking at 6.17 alone cannot see. The four earlier passes'
ground was deliberately not re-audited.

### [x] I11 — FIXED (same fix as I2) — the `kind="risk"` hand-off to 6.1 was never completed
`apps/procurement/models/RiskComplianceManagement/RiskSignals.py:206`

This is the same defect as **I2** (pass 1) reached from the other side, and the explorer found three
consequences pass 1 did not. `ALERT_KIND = "risk"` with its own comment block (lines 198-205)
explicitly handing the `KIND_CHOICES` + `kind_css` + `AlterField` work to Integrate — none of which
landed. **Both** alert raisers use it (`RiskSignals.py:689` and `Policies.py:469`, the latter
importing `ALERT_KIND`), so *every* alert 6.17 creates is affected.

The comment **understates** the damage as "the chip is simply the wrong colour". Actually:
1. `views/DashboardPortal/ProcurementAlerts.py:40,44` passes `kind_choices = KIND_CHOICES` to the
   filter — **no risk alert can ever be selected in the 6.1 inbox filter**.
2. `get_kind_display()` returns the bare string `risk` (Django returns the raw value for a
   non-choice), so 6.1's list and detail render an unlabelled kind.
3. `forms/DashboardPortal/ProcurementAlerts.py:20` has `kind` in `Meta.fields`, so a 6.17-raised
   alert **cannot be edited through 6.1's form** — the `<select>` has no `risk` option, so a save
   either fails validation or silently re-kinds the alert.

6.8 set the precedent correctly (`("contract","Contract")` + `0012_alter_procurementalert_kind`).
6.17 is the one module that raises a kind it never registered. **Merge with I2 when fixing.**

**[x] fixed — same commit as I2.** All three consequences the explorer listed were verified
closed at runtime, not reasoned about; see I2's note.

### [~] I12 — SKIPPED (verified: not a defect) — CORRECTED, NOT A DEFECT — "zero edits to 6.19's code" is accurate
The reviewer reported that `views/DocumentKnowledgeManagement/Policies.py:205-214` now reads
`obj.attestations.count()` and concluded the contract's "zero edits to 6.19's code" claim is false.
**Verified and refuted:** `git log -S "attestations"` on that file returns exactly one commit,
**`a093f2ae` "fix(procurement): gate policy delete and archive, and stop over-claiming what publish
guarantees"** — a **6.19-authored** commit. 6.17 made zero edits to it; the 6.19 session added that
guard themselves after `PolicyAttestation` landed.

So the contract is correct as a statement about what 6.17 did. What *is* true, and worth recording,
is the consequence the reviewer identified: **6.19 now hard-depends on 6.17** — removing 6.17 turns
`ppolicy_delete` into an `AttributeError`. The guard is right and must be kept (a `CASCADE` delete
of a policy would otherwise silently destroy every signature). No action for the fixer; recorded so
a future reader does not "correct" a doc that is accurate.

**[~] skipped — refuted by the reviewer who raised it; the contract is accurate.** Re-read and
agreed: nothing to change. Deliberately left alone rather than "fixed".

### [~] I13 — SKIPPED (routed to 6.19) — three 6.19 surfaces still say 6.17's ledger does not exist, one user-visible
6.17 shipped the ledger but every "when it ships" claim on the 6.19 side still stands:
- `models/DocumentKnowledgeManagement/Policies.py:22` — *"a bare flag with no machinery behind it …
  6.17 should collect acknowledgements for this one when it ships"*.
- `models/DocumentKnowledgeManagement/Policies.py:221-224` —
  `help_text="A hook for 6.17 … no sign-off ledger is built here."` **This renders on 6.19's policy
  form**, telling staff no ledger exists beside a checkbox that now governs one. (Changing it needs
  an `AlterField`.)
- `views/DocumentKnowledgeManagement/Policies.py:19-21` — *"3. No acknowledgement ledger exists."* —
  contradicted by line 214 of the same file.
- `templates/procurement/documentknowledge/policy/detail.html:89` — **user-visible**: *"collected by
  Policy Management & Acknowledgment (6.17) when it ships — no sign-offs are recorded here"*.

Also a **missed reciprocal link**: 6.17 links *to* `ppolicy_detail` eight times; 6.19's policy
detail links back nowhere — yet `apps/core/navigation.py:1664` asserts *"The two pages link to each
other"*. Only one direction is true.

**These are 6.19's files.** 6.17 must not edit them (contract §6a). **Route to the 6.19 session by
message**, and fix only the over-claim in 6.17's own `navigation.py` comment.

**[~] skipped — routed to the 6.19 session; only 6.17's own over-claim corrected.**
The four stale surfaces (`models/DocumentKnowledgeManagement/Policies.py:22` and `:221-224`,
`views/DocumentKnowledgeManagement/Policies.py:19-21`,
`templates/procurement/documentknowledge/policy/detail.html:89`) are 6.19's files under contract
§6a and were **not touched** — one of them additionally needs an `AlterField` on that model's
`help_text`, which is theirs to generate. Fixed here:
`docs(core): correct the 6.17/6.19 cross-link claim to one direction` — `apps/core/navigation.py`
no longer claims "The two pages link to each other"; it now records that 6.17 links to
`ppolicy_detail` eight times and the return link is 6.19's to add. Surgical two-line `Edit` on a
shared file, no rewrite.

### [x] M23 — FIXED — seal coverage and register scope disagree, and no page says so
`AuditSeals.py:317-320` — `seal_now()` hashes `AuditLog.objects.filter(tenant=tenant, id__gt=…)`,
i.e. **every** audit row in the workspace including `core`/`hrm`/`crm`/`accounting`. The register it
sits on shows only `procurement_activity_qs()`. It **over**-covers, so it is not a false security
claim — but `obj.row_count` will visibly exceed anything the register can show for the same window,
with no explanation. One sentence on `audit_trail.html` / `auditseal/list.html`.
**[x] fixed** — `docs(procurement): say on the seal register that a seal covers every module` +
`… say on the audit trail that a seal is wider than the register`. One paragraph on each page,
placed in the card a reader who noticed the discrepancy would already be reading. Both verified
present at 200.

### [x] M24 — FIXED — contradictory adjacent seeder comments
`seed_procurement.py:343` says *"6.18 runs LAST because…"*; six lines later `_seed_risk_compliance`
runs after it. 6.17 inserted itself **correctly** (the seal must be last), but did not amend 6.18's
claim. The next sub-module appending here reads "6.18 runs LAST", inserts in the wrong place, and
silently pushes its rows outside the seal.
**[x] fixed** — `docs(procurement): correct the seeder's stale "6.18 runs LAST" claim`. 6.18's
comment now describes what is actually true of it, 6.17's says it runs LAST, and an explicit
instruction was added for the next author (**insert ABOVE the `_seed_risk_compliance` call**) with
the consequence spelled out. Re-running the seeder is still a clean skip for every block.

### [x] M25 — FIXED — stale sub-package docstring
`models/RiskComplianceManagement/__init__.py` lists only `Screenings` as its entity module;
`RiskSignals`, `FraudAlerts`, `Policies` and `AuditSeals` are missing.
**[x] fixed** — `docs(procurement): list all five 6.17 entity modules in the sub-package init`.
All five listed with one line each. Docstring-only file, so nothing importable changed.

### Per-area verification record — what was checked and found clean

**1. Spine duplication — CLEAN, the strongest result in the review.** `grep -rn "^class "` over all
13 apps: 6.17 declares exactly six models, and `uniq -d` over every procurement model/form/view name
returns **empty** — no duplicate class name anywhere in the repo.
- **`ProcurementPolicy`:** no second model; FK'd **by string** with `related_name="attestations"`.
  `requires_acknowledgment` **genuinely governs** the roster — refusal at `Policies.py:206`,
  re-checked in the view (`:208`, `:368`) and reflected in templates that hide the button. Real, not
  decorative.
- **`VendorSuspension` (6.4):** no second block flag and, better than required, 6.17 **never writes
  it at all** — only reads `blocking_for()` and links out to `vsu_create`.
- **`MaverickSpendFinding` (6.14): zero overlap.** 6.17's six `RULE_CHOICES` intersect none of
  6.14's eight `REASON_CHOICES`; `split_purchase` stays 6.14's and is explicitly deferred to
  `maverick_dashboard`.
- **`scm.SupplierRiskAssessment` (4.2), `scm.ComplianceRequirement` (4.12), 6.13 duplicate-invoice,
  `hrm.HRPolicy`:** all cited, none duplicated.
- **No `related_name` collisions:** the four `related_name="fraud_alerts"` sit on four *different*
  target models.

**2. Cross-links real, not decorative — CLEAN with one note.** All 57 distinct `{% url %}` names and
15 `reverse()` targets resolved against actual `name=` declarations; **all 15 external targets
exist** and are called with the correct object's pk. Non-obvious win: `audit_trail.html:196` →
`activity_detail` is correct because `activity_detail` re-narrows to the *same*
`procurement_activity_qs()` base 6.17's register uses, so no listed row can 404. **Note (not a
defect):** the fraud *board* links to `dashboard`/`fraud_scan`/`fraudalert_list`/`vsu_list`, not to
`supplierinvoice_list`/`maverick_dashboard` as the brief expected — those two integrations exist on
`fraudalert/detail.html` and `fraud_scan.html` instead.

**3. Writes outside its own tables — CLEAN.** Every write targets a 6.17 table except two
`ProcurementAlert.objects.create(...)` calls, both permitted and matching the app-wide pattern
(6.3/6.8/6.19 do the same). `FraudAlert.scan()` reads `core.Party`/`Address`/`ContactMethod`
`filter(tenant=tenant)` read-only and **never edits, merges or deactivates a Party**. No
`VendorSuspension` write. `AuditSeal` only reads `core.AuditLog`.

**4. Sidebar staff-reachability (L32) — CLEAN.** All five destinations carry **`@login_required`
only**, no `@tenant_admin_required`: `screening_list`, `risksignal_list`, `audit_trail`,
`fraudalert_list`, `policy_list`. An ordinary tenant member reaches all five and sees data.
`policy_mine` is `@login_required` and reachable from three template links — the staff self-service
page works as intended. **No sidebar bullet redirects a non-admin.** Admin gating appears only on
destructive/adjudicating verbs. Two harmless consistency notes: `auditseal_create` omits an explicit
`@login_required` but `tenant_admin_required` wraps it internally (`core/decorators.py:15`) — **not
a bug**; and `screeninghit_delete` lacking the admin gate is already I1.

**5. Re-export completeness — CLEAN, verified by set-diff not by eye.** Models 6/6, forms 9/9,
views **48 defined ↔ 48 imported ↔ 48 in `__all__`**, diffed **both** directions — no missing name
and **no stale name**. `uniq -d` over all ~700 procurement view/model/form/`__all__` names: empty,
so no collision with another session's work.

**6. URL segments — CLEAN.** All 14 first segments grepped across the other 73 url modules: each is
claimed by a `RiskComplianceManagement/` file **and nothing else**. Literal-before-`<int:pk>` holds
in every module (`audit-seals/seal/`, `fraud-alerts/add/`, `risk-signals/add/`, `screenings/add/`).
`procurement-policies/` vs `policies/` and `receipt-audit/` vs `audit-trail/` are whole distinct
path components — Django anchors each `path()` prefix, so no prefix ambiguity. The app's one greedy
converter (6.8's `contract-sign/<str:token>/`) is scoped behind a literal first segment.

**7. Docs vs. reality — I12/I13/M23/M24/M25 above.** Verified *accurate*: contract §6's reuse list
matches the built FKs exactly; the "not buildable" vendor bank-detail note is honestly surfaced on
`fraud_scan.html`; the tamper-EVIDENT-not-tamper-proof framing is consistent across the model
constant, the view and all three seal/trail templates; migration `0028` creates exactly the six
models and nothing else.

---

## Pass 6 — qa-smoke-tester (RUNTIME)

**188 assertions across 9 areas, run twice back to back, identical both times: 186 passed, 2 failed.**
Every write ran inside one outer `transaction.atomic()` always rolled back via a sentinel exception,
each area on its own savepoint; throwaway objects carried `uuid4`-suffixed identifiers.
**Debris attributable to this pass: 0** (prefix sweep over 11 model/field pairs, all zero; acme's
6.17 counts match baseline exactly). Rollback proven to cover `django_session` rows written by
`force_login` (2495 → 2496 → 2495).

| # | Area | Checks | Result |
|---|---|---|---|
| 1 | Screening lifecycle | 24 | PASS |
| 2 | `FraudAlert.scan()` | 15 | 2 failed (F1/F2 below) |
| 3 | `policy_raise_attestations` | 14 | PASS |
| 4 | `attestation_sign` owner-only | 8 | PASS |
| 5 | Audit seal | 20 | PASS |
| 6 | Non-admin reachability | 17 | PASS |
| 7 | Pagination | 56 | PASS |
| 8 | CSV export | 12 | PASS |
| 9 | Remaining write verbs | 22 | PASS |

**The counter-bypass proof (area 1).** `UPDATE open_hit_count=0, hit_count=0` then re-POST `clear`
→ **still refused**. The disposition guard genuinely consults a live query, not the cached counter.
`block()` stamped `suspension_id=47` and created **no** `VendorSuspension` (count 3→3);
`ComplianceScreening` has **zero BooleanFields**, so no second block flag exists anywhere.

**The seal's core claim holds — four independent tamper shapes (area 5).** On two throwaway tenants
with **interleaved** log ids: MODIFY `#6622` → `False`, *"BROKEN: audit entry #6622 has been
MODIFIED"* — **names the exact id**; DELETE → names the id and reports *"1 of 2 sealed entries are
missing"*; INSERT (moving a row into the sealed range) → names the id; and mutating tenant B's row
**inside A's sealed id range** left A's seal **valid** — an independent proof of tenant isolation.
Restoring the row made it valid again in both mutation cases (no false positive). Sealing twice with
no new rows returns a no-op, not an empty seal. The real seeded `ASL-00001` (3,716 rows, `#1–#6383`)
verifies read-only.

**Pagination under forced ties (area 7).** Every register padded past **three** pages with
deliberate ties on each primary sort column — including an `UPDATE` forcing an **exact `created_at`
tie** across 36 policies and 36 attestations, the precise defect `_policy_qs` fixed. All eight
registers: **0 repeats, 0 vanished** across every page walked (1,303 rows / 12 pages on
`audit_trail`). **The `d046eaee` fix holds under a forced tie and no other register has the defect.**

**Non-admin reachability proven, not reasoned (area 6).** A throwaway non-admin acme member got
**200 with content** on all five `LIVE_LINKS["6.17"]` destinations plus `policy_mine` and eight more
pages — not one redirect. Gates still hold for that user (`screening_clear` 403, `auditseal_create`
403). L32 clean by execution.

**Scan mutation proof (area 2).** Exact SHA-256 row-hash over every row of `core.Party`, `Address`,
`ContactMethod`, `PartyRole`, `VendorSuspension`, `ComplianceScreening`, `ScreeningHit`,
`scm.PurchaseOrder`, `scm.PurchaseRequisition` before/after → **0 drifted**; count-diff across every
model in `core`/`scm`/`procurement`/`accounts` → `{FraudAlert: +9}` and nothing else. The 401-day
window returned `{}` in **0 SQL queries** (`CaptureQueriesContext`) — refused arithmetically, range
never materialised (L40 §1 confirmed at runtime).

**CSV injection (area 8).** All five payloads neutralised with a leading apostrophe, including the
**TAB-hidden** `\t=HYPERLINK(…)`; the user-authored `changes` JSON column also passes through
`csv_safe` (14 cells).

### [~] M26 — PARTIALLY FIXED (page claim); row marker blocked on a migration — three seeded fraud alerts are not reproducible by the rules that claim to have raised them
Clearing acme's board and re-running `scan()` reproduces **9 of 12** keys. Missing in both tenants:
`vem:*:tax_id` (both parties have `tax_id=''` and share no address or contact — yet the row's
`matched_on` reads `"tax_id ****4821"`, a masked number **neither party has**), `dupven:*:name`
("Bidder One GmbH" / "Bidder Two BV" share no normalised name, tax id or address), and `nvrush:*`
(recognised invoices total 1,324.20 against a 25,000 / 30-day threshold).

`seed_procurement.py:~4419` **states this is intentional** (hand-raised through the same model path
the create form uses), so it is a demo-fidelity choice, not an oversight. Two consequences only
execution shows: (a) an operator pressing **Run scan** over the window those three are dated in is
told *"The rules ran and raised nothing new"* while three alerts on the board carry those rule
labels; (b) M27 below. **Fix:** either seed supporting data so the three keys are genuinely
reproducible, or mark hand-raised rows visibly as such on the board.

**[~] partially fixed — consequence (a) closed on the page; the row-level marker is blocked.**
`docs(procurement): say that a zero-raise scan does not contradict the board` — the scan page now
states that a hand-raised alert carries a rule label but is not reproducible by that rule, so a
register row labelled with a rule the scan just reported zero for is expected rather than a
contradiction. Verified rendering after a real POST.

**Neither of the reviewer's two options was taken, and why:** marking hand-raised rows **per row**
needs a new column on `FraudAlert` — the same `AddField`-without-a-migration problem that made
**M11** unshippable in this session; and re-seeding supporting data would reverse a choice
`seed_procurement.py` documents as intentional demo fidelity and could not be verified on this
database without `--flush`, which is forbidden here. **Hand-off:** whichever session generates the
outstanding migration can add a `raised_by_rule`/`source` flag and mark the rows properly.

### [x] M27 — FIXED (the claim, not the behaviour) — `fraudalert_delete`'s docstring makes a guarantee the code does not make
`views/RiskComplianceManagement/FraudAlerts.py:341-342`: *"A re-scan would in any case re-raise a
deleted OPEN alert on the next pass — the dedupe key is deterministic — which is why deletion is for
mistakes, not for disagreement."* All three M26 alerts are `open` and therefore deletable, and a
re-scan over their own window does **not** restore them — proven at runtime. The claim is true of
rule-raised alerts and false of hand-raised ones; as written it is unconditional. Same class as
commit `60759147`. **Fix:** qualify to "an alert the RULES raised", or drop the sentence.
**[x] fixed** — `docs(procurement): qualify fraudalert_delete's re-raise guarantee`. Qualified
rather than dropped, and the conclusion that follows is now drawn: deleting a hand-raised alert is
**final**, which is why the route is admin-gated. **The claim was fixed, not the behaviour** — the
code is right.

### Could not exercise — stated rather than glossed
- **`self_approval` has zero runtime coverage from seed data** — acme has **0** `RequisitionApproval`
  rows (the seeder skips the rule for that reason). The detector itself was proven correct with a
  synthetic approval (`approver_id == requisition.requester_id` → fired `selfapp:143`), as were
  `vendor_employee_match`, `duplicate_vendor` and `new_vendor_rush` when given supporting data.
  **All six detectors are correct; only two of six are exercised by the seeded workspace** — a
  coverage gap Phase 6 should close.
- `audit_trail` pages 13+ (walked 12 of ~44 to bound runtime; no repeats or gaps in what was walked).
- `MAX_SEAL_ROWS` (50,000) and `MAX_ROSTER_SIZE` (2,000) ceilings — refused to materialise that much
  data on a shared DB; both guards are simple arithmetic/`len()` comparisons.

---

## All six passes complete — consolidated worklist for the fixer

**Order: Critical, then Important, then Minor.**

- **C1** hit deletable out of a decided screening (+ `screeninghit_edit`, + the two templates)
- **C2** `auditseal_list` drags the previous seal 50k-pair JSON blob (drop the unused join)
- **I1** `screeninghit_delete` has no admin gate (route + hide control in both list templates)
- **I2 + I11 = ONE FIX** `kind="risk"` unregistered in `ProcurementAlert.KIND_CHOICES` (+ `kind_css` + `AlterField`)
- **I3** ungated `policyattestation_edit` (route gate + disable `policy`/`user` on an existing row)
- **I4** `risksignal_refresh_board` unbounded row load
- **I5** `screening_rescreen_board` unbounded row load
- **I6** `risksignal_list` N+1 on `reviewed_by`
- **I7** `fraudalert_list` N+1 on `resolved_by`
- **I8** `_screening_options` uncapped ledger dropdown (`[:200]`)
- **I9** `SupplierRiskSignal` missing `(tenant, -observed_on)` index
- **I10** three `confirm()` handlers need `|escapejs`
- **I13** four 6.19 surfaces still say the ledger does not exist — **ROUTE TO 6.19 BY MESSAGE, do not edit their files**; fix only the over-claim in 6.17 `navigation.py`
- **M1, M2, M4-M8, M9-M18, M19-M21, M23-M27** as listed in each pass
- **Skipped by decision:** M3 and M22 (app-wide patterns, L18/L28), I12 (refuted — no defect)


---

## OUTSTANDING MIGRATION — claimed by nobody, generate it in the main session

The fixer did **not** run `makemigrations` (cross-session announce protocol: three other sessions
share this checkout, and 6.16 already has an uncommitted index pending). These model changes are
committed and `manage.py check` is clean, but the schema does not yet match:

| From | File | Operation |
|------|------|-----------|
| I9 | `models/RiskComplianceManagement/RiskSignals.py` | `AddIndex` `prc_srs_tnt_obs_idx` on `SupplierRiskSignal(tenant, observed_on)`. Index-only, no data change. |
| I2/I11 | `models/DashboardPortal/ProcurementAlerts.py` | `AlterField` on `procurementalert.kind` — `KIND_CHOICES` gained `("risk", "Risk")`. Precedent: `0012_alter_procurementalert_kind`. Choices-only, no data change. |
| M15 | `models/RiskComplianceManagement/FraudAlerts.py` | `AlterField` on `fraudalert.document_date` (dropped `db_index=True`) **and** `AddIndex` `prc_frd_tnt_assignee_idx` on `(tenant, assigned_to)`. |
| M15 | `models/RiskComplianceManagement/AuditSeals.py` | `RemoveIndex` `prc_asl_tnt_sealed_idx`. |
| M15 | `models/RiskComplianceManagement/Policies.py` | `RemoveIndex` `prc_patt_tnt_policy_idx`. |

**Every operation above is choices-only or index-only, so the tree runs correctly without them** —
`manage.py check` is clean and the 253-check smoke sweep passes. **M11 is the exception and was
therefore NOT applied**: its `AddField` (`auditseal.last_verified_by`) changes every `SELECT` and
raised `OperationalError 1054` on every seal page, so it is left for a session that can generate
the migration in the same run.


---

## Fixer close-out

**39 findings, 0 left open: 36 `[x]` fixed, 6 `[~]` skipped** (M3 and M22 were already skipped by
decision before the fixer ran; I12 was already refuted; I13, M11 and M26 are the fixer's own
skips/partials, each with its reason recorded inline above).

**Verification at close:**
- `manage.py check` — **clean**, run after every single edit.
- `temp/smoke617.py` — **253 checks, 0 failures**, re-run repeatedly through the burn-down and at
  the end.
- Exploit proofs, each rolled back through a sentinel exception with `uuid4`-suffixed identifiers,
  each asserting the **row is unchanged** rather than only that a redirect happened:
  `temp/fix617_c1.py` 10/10 · `temp/fix617_i1.py` 8/8 · `temp/fix617_i3.py` 12/12 ·
  `temp/fix617_i2.py` 10/10.
- `apps/procurement/tests/test_portal_models.py` — 27 passed with the new `("risk", "Risk")`
  choice (its L33 badge tests iterate `KIND_CHOICES`, so they exercise the new value directly).

**`makemigrations` was deliberately never run** (cross-session announce protocol). Every schema
change committed is choices-only or index-only and the tree runs correctly without its migration;
see the OUTSTANDING MIGRATION table above. The one finding that could NOT be split that way — M11's
`AddField` — was written, proven to break every seal page with `OperationalError 1054`, and
**reverted rather than left half-applied**.

**One file per commit throughout**, each with `git add '<path>'; git commit --only '<path>'` so a
concurrent session's staged work could never be swept in.
