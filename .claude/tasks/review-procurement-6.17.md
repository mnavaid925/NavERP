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

### [ ] C1 — Critical — a hit can be deleted out of a *decided* screening, erasing the match the decision rests on
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

### [ ] I1 — Important — `screeninghit_delete` is the one delete verb with no admin gate, and it is the one that unlocks Clear
`apps/procurement/views/RiskComplianceManagement/ScreeningHits.py:227`

All four sibling deletes are `@tenant_admin_required` (`Screenings.py:295`, `RiskSignals.py:290`,
`FraudAlerts.py:334`, `Attestations.py:329`). `clear()` refuses while any hit is `open`.

**Failure scenario:** a non-admin analyst deletes the two open OFAC-SDN hits on SCR-00003; the
admin then opens a clean-looking screening, is offered the Clear button, and clears the supplier —
with nothing on the record showing a 93% SDN match was ever returned. Capture is analyst work;
destroying the match is not. **Fix:** add `@tenant_admin_required`, and hide the delete control
from non-admins in the two list templates (as `screening_delete` already does).

### [ ] I2 — Important — `ALERT_KIND = "risk"` is not in `ProcurementAlert.KIND_CHOICES`
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

### [ ] M1 — Minor — the fraud board's freshest ageing bucket excludes future-dated alerts
`apps/procurement/views/RiskComplianceManagement/FraudScan.py:274` — the comment claims the bucket
catches anything "dated today or (defensively) later"; the condition is `document_date__lte=today`
(line 270), so a future-dated open alert falls into no bucket and the board's counts sum to less
than `stats.open`. Reachable: `FraudScanForm` bounds `end` only relative to `start`. Fix: drop the
`__lte` bound on the `fresh` bucket.

### [ ] M2 — Minor — `screening_unresolved` evidence text misdescribes a `true_match`
`apps/procurement/models/RiskComplianceManagement/FraudAlerts.py:1221` — the sentence says the
screening "still carries a match nobody has adjudicated", but `_UNRESOLVED_DISPOSITIONS`
(line 211) includes `true_match`, which *has* been adjudicated. On an accusation naming a supplier,
that sentence is the one a reader quotes back. Fix: branch the wording on the disposition.

### [~] M3 — Minor — the six names appended to `PROCUREMENT_CONTENT_MODELS` are a no-op
`apps/procurement/views/_helpers.py:41-50` — the tuple is consulted only on the
`content_type__app_label="scm"` branch (lines 70-72); all six 6.17 models are
`app_label="procurement"` and are already matched unconditionally by the first `Q`. **Nothing is
broken** — the rows do reach the feed — but the comment reads as if the edit made them appear.
**App-wide pattern** (`procurementalert`/`eauction`/`rfxevent` above it have the same shape), so
flag rather than fork (L18/L28).

### [ ] M4 — Minor — `fraud_scan` is the only non-PRG POST in 6.17
`apps/procurement/views/RiskComplianceManagement/FraudScan.py:128-168` — re-renders on a
successful POST, so a browser refresh re-runs the scan. Benign (idempotent; a second pass raises 0
and writes no audit row), but `policy_overdue_board`, `policy_raise_attestations`,
`auditseal_create` and `auditseal_verify` all redirect. Fix: pop-once session key + redirect.

### [ ] M5 — Minor — two create forms have no L39 dead-end notice
`Screenings.py:240` and `RiskSignals.py:218` — in a workspace with no supplier `Party`, the
required `party` field renders as an empty `<select>` on an unsubmittable form.
`templates/.../attestation/form.html:56-64` handles the identical precondition correctly; copy it.

### [ ] M6 — Minor — the hit detail page instructs the user toward a control it never renders
`templates/procurement/riskcompliance/screeninghit/detail.html:131` says "If it was captured
wrongly, delete it and record it again" for an adjudicated hit, while the Delete card at line 136
is gated `{% if obj.is_open %}`. The view currently allows it (see C1) — pick one answer across
view, template copy and template gate.

### [ ] M7 — Minor — `BATCH_PARTY_LIMIT` is dead code
`apps/procurement/models/RiskComplianceManagement/Screenings.py:163,197` — referenced only from a
URL-module docstring, because `screening_batch` was deliberately cut. Drop the constant with the
feature.

### [ ] M8 — Minor — `form-input` on a `<textarea>`
`templates/procurement/riskcompliance/attestation/detail.html:127,136` — every other textarea in
the sub-module uses `form-textarea`; theme.css defines both.

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

### [ ] I3 — Important — ungated `policyattestation_edit` defeats the admin-gated withdrawal
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

### [ ] M9 — Minor — `matched_on` writes an employee's street address verbatim
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

### [ ] M10 — Minor — seal detail/verify are cheap, uncapped amplifications for the lowest-privilege user
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

### [ ] M11 — Minor — verification stamps have no actor, and a passing verify leaves no record
`apps/procurement/models/RiskComplianceManagement/AuditSeals.py:216-218` (surfaced at
`AuditTrail.py:523-526`) — no `last_verified_by`, and a pass writes no `AuditLog` row, so
`auditseal/detail.html` renders "Last full verification passed on …" with nobody's name on it, on a
route any member can trigger. On an evidence-grade record an auditor cannot tell whether a
responsible person ran the check. **Fix:** one nullable `last_verified_by` FK + pass `user` into
`verify()`.

### [ ] M12 — Minor — seals never cover `tenant IS NULL` audit rows
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

### [ ] M13 — Minor — operator-typed `matched_on` steers the detector's dedupe key
`apps/procurement/forms/RiskComplianceManagement/FraudAlerts.py:61-63`;
`models/.../FraudAlerts.py:453-461` — `_key_attribute()` derives the key's attribute segment from
`matched_on`'s first word, so a member can hand-raise a pair with `matched_on = "tax_id …"`,
producing exactly the key a later scan would compute. `_upsert` then only refreshes and never
re-opens a disposed alert, so a pre-emptive row disposed `unsubstantiated` means the real detection
can never surface as open. Not a privilege escalation (an admin could dispose it anyway); the
difference is the finding is never *visible* as open to anyone else. **Fix:** `_key_attribute()`
returns `"manual"` for hand-raised rows so they can never collide with the detector's key.

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
