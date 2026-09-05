# Contract — procurement 6.17 Risk & Compliance Management

**Frozen 2026-09-05, Phase 3 step 1.** Derived from `.claude/tasks/todo.md` (§ "Sub-module 6.17")
and `.claude/tasks/research-procurement-6.17.md`. Where the plan and the as-built code disagreed,
**the code wins and the resolution is recorded below.**

This file exists for one reason: **a name left unpinned is a silently blank region or a
`NoReverseMatch` (L7/L8).** Every name a template consumes is pinned here.

---

## 0. Drift resolved against the as-built code (read this first)

| Plan said | As-built truth | Resolution |
|---|---|---|
| list context `objects` | `apps/core/crud.py:crud_list` renders **`object_list`**; 43 procurement templates use `object_list`, **0** use `objects` | **`object_list`.** The plan's `objects` is drift — never emit it. |
| — | `crud_detail`/`crud_edit` render **`obj`**; `crud_create`/`crud_edit` render **`form` + `is_edit`** | Pinned below; do not rename. |
| `log_action` (Phase-1 brief) | `apps.core.utils.write_audit_log(user, obj, action, changes=None, tenant=None)` — 987 call sites; **`log_action` does not exist** | Use `write_audit_log`. |
| sub-package unnamed | siblings are PascalCase NavERP titles | **`RiskComplianceManagement/`** in all four layers; templates `templates/procurement/riskcompliance/`; test subslug **`riskcompliance`**. |
| Entity 4 declares `ProcurementPolicy` | **`procurement.ProcurementPolicy` ALREADY EXISTS** — 6.19 shipped it (commit `dfa7cc99`) at `models/DocumentKnowledgeManagement/Policies.py:152`, prefix `[PPOL-]`, already re-exported. A second one raises `RuntimeError: Conflicting 'procurementpolicy' models in application 'procurement'` | **Entity 4 builds the LEDGER ONLY** — see §6a. |

**Import rule for a not-yet-wired entity** (house pattern, copied from
`views/BudgetCostManagement/BudgetMappings.py:30`): inside this sub-package import the entity
MODULE directly — `from apps.procurement.models.RiskComplianceManagement.Screenings import
ComplianceScreening` — **never** `from apps.procurement.models import ComplianceScreening`, which
is a star-import cycle at URLconf import time until the Integrator lands the re-export.

---

## 1. Context-var contract (the L7 pin)

### Supplied by `apps/core/crud.py` — NEVER re-name these

| view kind | keys |
|---|---|
| `crud_list`   | `object_list`, `page_obj`, `q` (plus this view's `extra_context`) |
| `crud_detail` | `obj` (plus `extra_context`) |
| `crud_create` | `form`, `is_edit=False` (plus `extra_context`) |
| `crud_edit`   | `form`, `obj`, `is_edit=True` (plus `extra_context`) |
| `crud_delete` | redirect only — no template |

Pagination is `page_obj` with `page_obj.window`; templates guard prev/next with
`has_previous`/`has_next` (L9).

### `extra_context` per page — the exhaustive list

- **`screening_list`** → `list_source_choices`, `checkpoint_choices`, `result_choices`,
  `status_choices`, `parties`, `stats` (`.pending .open_hits .blocked .rescreen_due`), `is_admin`,
  `retention_note`
- **`screening_detail`** → `hits`, `open_hits`, `allowed_actions`, `blocking_suspensions`,
  `hit_form`, `disposition_choices`, `is_admin`, `retention_note`
- **`screening_create` / `screening_edit`** → nothing beyond the crud keys
- **`screening_rescreen_board`** → `rows`, `stats` (`.overdue .due_soon .total`), `today`, `is_admin`
- **`screeninghit_list`** → `disposition_choices`, `list_source_choices`, `match_type_choices`,
  `screenings`, `stats` (`.open .true_match .false_positive`), `is_admin`
- **`screeninghit_detail`** → `screening`, `allowed_dispositions`, `disposition_form`, `is_admin`
- **`risksignal_list`** → `provider_choices`, `metric_choices`, `band_choices`, `trend_choices`,
  `review_status_choices`, `parties`, `stats` (`.critical .deteriorating .unreviewed .refresh_due`),
  `is_admin`
- **`risksignal_detail`** → `series`, `scale`, `breaches_minimum`, `minimum_acceptable`,
  `assessment` (latest `scm.SupplierRiskAssessment`, may be `None`), `alert`, `is_admin`
- **`risksignal_refresh_board`** → `rows`, `stats` (`.overdue .due_soon .stale`), `today`, `is_admin`
- **`fraudalert_list`** → `rule_choices`, `status_choices`, `severity_choices`, `vendors`, `users`,
  `stats` (`.open .investigating .confirmed .high`), `is_admin`
- **`fraudalert_detail`** → `sources` (list of `{label, value, url}`), `allowed_actions`,
  `disposition_form`, `blocking_suspensions`, `is_admin`
- **`fraud_scan`** → `form`, `results` (`{rule_value: count}`, or `None` on GET), `rule_labels`,
  `skipped_groups`, `capped`, `scan_limits`, `not_buildable_note`, `is_admin`
- **`fraud_board`** → `by_rule`, `by_severity`, `ageing`, `rule_labels`, `citation_invoice_url`,
  `citation_maverick_url`, `stats`, `is_admin`
- **`policy_list`** → `category_choices`, `status_choices`, `org_units`, `stats`
  (`.published .draft .attestation_due`), `is_admin`
- **`policy_detail`** → `attestations`, `attestation_stats` (`.target .attested .outstanding .rate`),
  `supersedes`, `superseded_by`, `allowed_actions`, `is_admin`
- **`policy_mine`** → `rows`, `stats` (`.pending .overdue .signed`), `today`
- **`policy_overdue_board`** → `rows`, `stats` (`.overdue .due_soon`), `today`, `is_admin`
- **`policyattestation_list`** → `status_choices`, `policies`, `users`, `stats`
  (`.pending .overdue .acknowledged`), `is_admin`
- **`policyattestation_detail`** → `policy`, `can_sign`, `allowed_actions`, `is_admin`
- **`audit_trail`** → `object_list`, `page_obj`, `q`, `action_choices`, `content_types`, `users`,
  `retention_note`, `chain_status`, `tamper_note`, `export_query`
- **`auditseal_list`** → `stats` (`.seals .verified .broken`), `chain_status`, `is_admin`
- **`auditseal_detail`** → `entries_covered`, `verification`, `is_admin`

`is_admin` gates the Actions column so a non-admin is never shown a button the view will refuse.

---

## 2. Files — one entity group per file, four layers lined up

```
apps/procurement/{models,forms,views,urls}/RiskComplianceManagement/
    __init__.py
    Screenings.py       ComplianceScreening + ScreeningHit          [SCR-]
    RiskSignals.py      SupplierRiskSignal                          [SRS-]
    FraudAlerts.py      FraudAlert                                  [FRD-]
    Policies.py         ProcurementPolicy + PolicyAttestation       [PPL-]
    AuditSeals.py       AuditSeal   (LAST + CUTTABLE)               [ASL-]
```

`urls/` additionally splits `ScreeningHits.py`, `Attestations.py`, `FraudScan.py` and
`AuditTrail.py` so each `urlpatterns` sits next to the views it routes. **Literal routes before
`<int:pk>`** — `screenings/batch/` and `audit-seals/seal/` must precede their pk routes.

---

## 3. URL names (namespace `procurement`) — these ARE the contract

`screening_list` `screening_create` `screening_detail` `screening_edit` `screening_delete`
`screening_clear` `screening_escalate` `screening_block` `screening_rescreen_board`
`screening_batch`*

`screeninghit_list` `screeninghit_create` `screeninghit_detail` `screeninghit_edit`
`screeninghit_delete` `screeninghit_dispose`

`risksignal_list` `risksignal_create` `risksignal_detail` `risksignal_edit` `risksignal_delete`
`risksignal_review` `risksignal_refresh_board`

`fraudalert_list` `fraudalert_create` `fraudalert_detail` `fraudalert_edit` `fraudalert_delete`
`fraudalert_disposition` `fraud_scan` `fraud_board`

`policy_list` `policy_detail` `policy_mine` `policy_overdue_board` `policy_raise_attestations`
— **amended, see §6a.** `policy_create` `policy_edit` `policy_delete` `policy_publish`
`policy_archive` `policy_new_version` are **NOT built by 6.17**: 6.19 already owns the authoring
surface for this table (`ppolicy_create/_edit/_delete/_publish/_archive`).

`policyattestation_list` `policyattestation_create` `policyattestation_detail`
`policyattestation_edit` `policyattestation_delete` `attestation_sign` `attestation_exempt`

`audit_trail` `audit_trail_export` `auditseal_list` `auditseal_detail` `auditseal_create`
`auditseal_verify`

`*` cuttable. **No `auditseal_edit`, no `auditseal_delete`** — a seal that can be edited is not a
seal. Documented deviation from the CRUD-completeness rule; the reason is stated on the page.

---

## 4. Templates — `templates/procurement/riskcompliance/`

`screening/{list,detail,form}.html` · `screeninghit/{list,detail,form}.html` ·
`risksignal/{list,detail,form}.html` · `fraudalert/{list,detail,form}.html` ·
`policy/{list,detail}.html` (**no `form.html`** — 6.19 owns authoring, §6a) ·
`attestation/{list,detail,form}.html` ·
`auditseal/{list,detail}.html` (no form — creation is a POST button)

Sub-module-root standalone pages: `rescreening_due.html` `risk_refresh_due.html` `fraud_scan.html`
`fraud_board.html` `policy_overdue.html` `my_policies.html` `audit_trail.html`

**Theme classes — confirm in `static/css/theme.css` before writing any template (L33/L40):**

- badges: `badge-green badge-red badge-amber badge-info badge-muted badge-slate` ONLY
- detail pages: `<dl class="detail-grid"><div class="detail-item"><dt>..</dt><dd>..</dd></div></dl>`
  — **`.detail-label`/`.detail-value` do not exist** (L40 §2)
- `confirm()` copy escapes apostrophes as `\'`, never `&#39;`, and **never interpolates a
  user-typed value** (L42) — use the `SCR-`/`SRS-`/`FRD-`/`PPL-` number
- FK filter comparison `{% if request.GET.party == p.pk|stringformat:"d" %}` — never `|slugify`
- no `|safe` on `matched_on`, `detail`, `target`, `changes` or `source_ref` — all staff-authored text

---

## 5. Forms — `Meta.fields` is a whitelist; the exclusions are the contract

Blanket rule enforced at review: **no form carries** `tenant`, an auto-`number`, a `*_by`/`*_at`
system stamp, a workflow-controlled `status`/`disposition`/`review_status`, a derived
score/band/trend/count/digest, or `dedupe_key` (L20/L22/L28). Per-form field lists live in
`todo.md` § "Forms" and are authoritative.

Every ModelForm subclasses `TenantModelForm` (`apps/core/forms/_common.py`), takes `tenant=`, and
calls `_reject_foreign(self, cleaned, [<every FK>])` so a crafted POST cannot reach another
tenant's row.

---

## 6. Reuse — FK by string, never re-declare (L29/L36/L37)

`core.Party` · `core.Document` · `core.OrgUnit` · `core.AuditLog` · `settings.AUTH_USER_MODEL` ·
`scm.PurchaseRequisition` · `scm.PurchaseOrder` · `procurement.VendorSuspension` (6.4 — the ONLY
block flag) · `procurement.RequisitionApproval` (6.3) · `procurement.ProcurementAlert` (6.1) ·
`procurement.SupplierInvoice` (6.13).

Cited, never duplicated: `scm.SupplierRiskAssessment` (4.2 composite score),
`scm.ComplianceRequirement`/`ComplianceCheck` (4.12), `procurement.MaverickSpendFinding` (6.14 —
copy the `scan()`/`dedupe_key` SHAPE, none of its eight reasons), 6.13 duplicate-invoice detection.

### 6a. Ownership call — 6.19 owns `ProcurementPolicy`; 6.17 owns the attestation ledger

**Decided 2026-09-05, mid-build, by the ships-first rule (L36/L29/L37).** 6.19 Document &
Knowledge Management shipped `procurement.ProcurementPolicy` [PPOL-] before 6.17 reached Entity 4.
Django permits one model of a name per app, so the plan's second `ProcurementPolicy` is not merely
duplicative — it **cannot load**:

```
RuntimeError: Conflicting 'procurementpolicy' models in application 'procurement'
```

This is not a naming accident. 6.19's own model docstring reserves this work for 6.17 in as many
words: *"Policy Management & Acknowledgment is 6.17's sub-module, and it owns the acknowledgement
ledger"*, and its `requires_acknowledgment` field is documented as *"a bare hook … 6.17 should
collect acknowledgements for this one when it ships"*. So the two modules already agree; only the
6.17 plan — written before 6.19 landed — was out of date.

**The split, now fixed:**

| | owns |
|---|---|
| **6.19** | the policy table itself: authoring, versioning (`previous_version`), publish/archive verbs, the `ppolicy_*` register |
| **6.17** | the **acknowledgement ledger**: `PolicyAttestation`, who was assigned, who signed, when, who is overdue, and the exemption path |

**Consequences, all reflected above:** 6.17 declares **`PolicyAttestation` only**, FK'ing
`"procurement.ProcurementPolicy"` **by string** — it never re-declares the policy. The authoring
verbs are dropped. Because 6.17 must not edit 6.19's files, "publish raises the roster" is
inverted into a 6.17-owned idempotent admin verb, **`policy_raise_attestations`**, which raises the
roster for an already-published policy — **zero edits to 6.19's code**. 6.19's model has no
`attestation_due_days`, so `due_on` derives from a 6.17-owned `DEFAULT_ATTESTATION_DUE_DAYS = 14`.

Bullet 5 is still fully served, and by a better division than the plan had: one policy library, one
sign-off ledger, no second register competing for the same concept.

**Not buildable, and the page says so:** the vendor bank-detail-change fraud rule —
`accounting.VendorProfile` has no bank fields and `accounting.BankAccount` is the tenant's own
account. Stated on `fraud_scan.html` rather than silently omitted.

---

## 7. Migration

Procurement leaf on disk at freeze time:
`0025_remove_budgetmapping_prc_bmap_tnt_active_idx_and_more`. A concurrent session is building
**6.16 and takes `0026_*`** — 6.17 runs `makemigrations` only **after** their file lands, and takes
**`0027_*`** (L43). Do not generate before then.

---

## 8. Definition of done

`makemigrations` + `migrate` clean · `seed_procurement` idempotent run **twice** (never `--flush`,
L43/L46) · `manage.py check` clean · every page 200 as `admin_acme`/`password` with a **content**
assertion (L8/L41) · every valid filter value returns the right ROWS, not merely 200 (L44) ·
cross-tenant IDOR → 404 · `LIVE_LINKS["6.17"]` maps five bullets to five **distinct** staff pages
(L30/L32).
