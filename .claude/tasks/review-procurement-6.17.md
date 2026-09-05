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
