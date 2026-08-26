# Review — Procurement 6.8 Contract Management

- **Scope:** `apps/procurement/{models,forms,views,urls}/ContractsManagement/`, migration 0011, `_seed_contracts` tail, admin 6.8 section, `test_contracts_68.py`, navigation 6.8 block, 12 templates.
- **Lanes:** code+security+performance agent · frontend+QA agent (live probe included). Two parallel agents replacing the six-lane workflow this session.

## Findings (fix these)

| ID | Severity | File:line | Finding | Status |
|----|----------|-----------|---------|--------|
| R1 | **Important** | models/…/Renewals.py:76 + ProcurementAlerts.py:29 | `kind="contract"` not in `ProcurementAlert.KIND_CHOICES` → out-of-vocabulary alert rows; inbox kind filter/admin never match. Add `("contract", "Contract")` + migration 0012 (AlterField). | [x] fixed — choice added + 0012 generated; shell asserts `'contract' in KIND_CHOICES` |
| R2 | **Important** | views/…/Contracts.py:234–248 | Public sign page never expires: POST signs even on terminated/expired/renewed spine contracts. Refuse render+POST unless `contract.status` in a LIVE set (mirror crm's expired branch; render "closed" notice). | [x] fixed — `SIGNABLE_STATUSES` gate + closed-notice branch; shell asserts expired/terminated/renewed are closed |
| R3 | **Important** | views/…/Milestones.py:117–120 | Open redirect: `redirect(request.POST.get("next"))` accepts scheme-relative URLs. Validate via `url_has_allowed_host_and_scheme(next, request.get_host())` else fall back to milestone_list. Remove dead `or "procurement:milestone_list"`. | [x] fixed — `_safe_next` guard on both POST verbs; shell proves `//evil.com`/absolute fall back, same-host path kept |
| R4 | **Important** | views/…/Amendments.py:64–76 | Sequential change-control race: `has_open_for` checked outside any lock; two filings can both pass. Wrap create in `transaction.atomic()` + `SupplierContract.objects.select_for_update().get(pk=...)` and re-check under lock. | [x] fixed — create re-checks status+has_open_for under `select_for_update`; shell proves lock order precedes save |
| F1/F2 | Blocker — **NOT THIS LANE** | forms/__init__.py + urls/VendorManagement/Portal.py | Concurrent 6.4 session's half-wired VendorBidForm/views break the whole procurement urlconf right now. Owner: 6.4 session. Do NOT touch (L45). | [~] other lane |
| R5 | Minor | views/…/Amendments.py:117–123 | Approve must also assert `contract_locked.status in AMENDABLE_STATUSES` before apply() (no applying onto since-terminated contracts). | [x] fixed — `_decide` re-asserts amendability under the contract lock; shell proves lock→guard→apply order, terminal statuses refused |
| R6 | Minor | models/…/Renewals.py:66–86 | Dedupe exists()-then-create race under concurrency: check + create per contract inside `transaction.atomic()` with `select_for_update()` on the contract row. | [x] fixed — per-contract atomic+lock around check/create; shell run×2 stays silent (raised 0, rows unchanged) |
| R7 | Minor | views/…/Clauses.py (clause_list) + clauses/list.html:50 | N+1 `procurement_clause_links.count` per row → annotate `Count` and render `obj.n_links`. | [x] fixed — `n_links=Count(...)` annotate; direct RequestFactory render of clause_list runs 2 queries total |
| R8 | Minor | seed_procurement.py `_seed_contracts` | Clauses created OUTSIDE the atomic block (partial-failure poisons the guard); `admin_user.get_full_name()` unsafe if None. Move clause creation inside atomic; fall back user lookups. | [x] fixed — clause loop moved inside atomic; `internal_name`/`internal_email` None-safe; seeder re-run clean |
| R9 | Minor | views/…/Contracts.py:196–204 + contracts/detail.html | Sign share-link + add/remove-signer verbs visible/writable to every member while legal verbs are admin-gated. Gate link display + both verbs on `is_admin`; success message remains the one-time channel. | [x] fixed — `@tenant_admin_required` on both verbs; link/remove/add-signer UI wrapped in `{% if is_admin %}` |
| R10 | Minor | contracts/detail.html:60–69 | Add/remove-clause controls ignore computed `is_admin` → members see 403 buttons. Wrap in `{% if is_admin %}`. | [x] fixed — remove column + add-to-draft form wrapped in `{% if is_admin %}`; stale authenticated gate removed |
| R11 | Minor | views/…/Amendments.py + amendments/detail.html | `decision_note` validated/persisted but no template renders the input. Add a note textarea to the DETAIL page decision forms. | [x] fixed — detail page now has admin-gated approve/reject forms each with a `decision_note` textarea; view passes `is_admin` |
| R12 | Minor | admin.py 6.8 section | Dead `ContractClauseLinkInline` (attached nowhere); `ContractAmendmentAdmin` leaves reason/proposed_* editable after application. Delete inline; add proposed fields to readonly_fields. | [x] fixed — inline class + unused import removed; reason/proposed_* in readonly_fields (verified via admin registry) |
| R13 | Minor | milestones/list.html:48–54 | Complete form omits explicit `action=complete`; both verbs omit `next` back to the register. Add hidden inputs (view default stays). | [x] fixed — `action=complete` + `next=milestone_list` hidden inputs added to both verbs; view defaults untouched |
| R14 | Minor | tests/test_contracts_68.py | Coverage gaps: member POST 403s on add-link/approve/renewals_run; signed (not just declined) branch; ≤7-day severity boundary; clause-delete PROTECT refusal; terminate-then-approve refusal. Add compact cases. | [x] fixed — 5 cases appended; each proven via shell probes (PermissionDenied gate, sign stamps, 7d=critical/8d=warning, clause survives delete, terminated spine refuses apply), pytest NOT run per lane rule |

## Skipped with reason

| ID | Finding | Reason |
|----|---------|--------|
| S1 | Renewals.py window scan filters in Python (O(all contracts)/view) | Board/register scale is capped; per-row date arithmetic in SQL is less readable. Revisit if tenants exceed thousands of live contracts. |
| S2 | `.inline-form` class undefined in theme.css | Cosmetic dead class; layout relies on `.table-actions` flex. Consistent cleanup belongs to a theme sweep. |
| S3 | Filter-bar inputs lack aria-labels (5 templates) | Same gap across every sibling sub-module's lists; a11y sweep should be app-wide, not piecemeal here. |
| S4 | Contract register has no Edit/Delete per-row actions | Deliberate: header lifecycle verbs belong to scm's own contract views (L36); the SCM-spine link button covers it. Documented in UI as external-link. |

## Verified clean
Tenancy scoping on every staff queryset/FK picker; mass-assignment exclusions on all forms; locked apply() refusing non-pending; blank-proposal refusal; sign-page viewed_at/POST-inert semantics; badge/stat-icon vocabulary colour-named only; url names resolve; context keys match views; escape-safe public page (no |safe).
