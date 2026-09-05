# Review — Procurement 6.19 Document & Knowledge Management

Six reviewers, run one after another (CLAUDE.md Module Creation Sequence, Phase 4). Each appends
its findings here as it reports; the file is deduped, sorted and given IDs once all six are in.

**Scope** — by PATH, not a commit range. Four sessions (6.16/6.17/6.18/6.19) built into this same
checkout today, so `git diff <base>..HEAD` returns the wrong code.

```
apps/procurement/{models,forms,views,urls}/DocumentKnowledgeManagement/*.py   20 files
templates/procurement/documentknowledge/*/*.html                             12 files
```

plus the 6.19-only blocks of: the four package-root `__init__.py`, `admin.py`,
`seed_procurement.py` (`_seed_document_knowledge` + its `--flush` lines), `navigation.py`
(`LIVE_LINKS["6.19"]`), and the 6.19 operations in `migrations/0026_*.py` (that migration also
carries 6.16 four models — out of scope).

**Prior gate:** smoke sweep green — 37 route probes, 0 failures, all 10 checks (content asserted,
filters diffed against the ORM, cross-tenant IDOR to 404 on all four models, revision chain
forward-only rule confirmed, page 2 forced with synthetic rows).

**Deliberate boundaries — not findings:** advisory-only spend thresholds (6.3 enforces);
`requires_acknowledgment` a bare hook (6.17 owns attestation, `PolicyAttestation` already FKs this
model); OCR / semantic search / folder trees / retention destruction are Module 13.

---

## Pass 1 — `code-reviewer` (correctness, tenancy, authz, structure, integrity)

Verified 20 Python + 12 templates against the contract; `makemigrations --check` "No changes
detected"; all 37 `{% url %}` names resolve. **Verdict: no Critical; four Important.**

### Critical

None. Every queryset tenant-scoped, every model has a tenant FK, every verb `@require_POST`, no
form exposes a view-owned/system field, no missing migration.

### Important

**[ ] 1 — `admin.py:831` `ProcurementPolicyAdmin.search_fields` names a field that does not exist.**
`"tags"` was copied from `KnowledgeResourceAdmin:844`, where it does exist. Typing anything into
the policy admin search box raises `FieldError: Cannot resolve keyword 'tags' into field`
(reproduced against the real model). `manage.py check` does **not** validate `search_fields`, so
the hooks let it through.
*Fix:* `("number", "title", "summary", "body", "version_number")`.

**[ ] 2 — `views/DocumentKnowledgeManagement/Documents.py:424-425` re-index can permanently install a SUPERSEDED revision text.**
The Run blind-overwrites the parent search copy after a slow file read.
*Scenario:* doc D has pointer=2, `extracted_text=""`. Admin A presses Re-index; the loop reads r2
and spends seconds in `pdfplumber`. Admin B approves r3, so pointer=3 and r3 text is written. A
then executes `document.save(update_fields=["extracted_text", "updated_at"])` with **r2 text**. The
pointer says r3, search matches r2, and re-index never revisits it because `extracted_text` is no
longer `""`.
*Fix:* conditional write instead of a blind save — filter on
`pk`, `tenant`, `extracted_text=""` **and** `current_revision_no=document.current_revision_no`,
then `.update(...)`, counting `indexed` only when it returns 1.

**[ ] 3 — `views/DocumentKnowledgeManagement/Revisions.py:432-447` `pdocrevision_delete` guards an UNLOCKED snapshot.**
Approve does the same work under `select_for_update()`; delete does not.
*Scenario:* pointer=2, r3 pending. B POSTs delete on r3 (reads `is_approved=False`, pointer=2 —
both guards pass); A concurrently approves r3, so pointer=3; B `revision.delete()` runs. The
document now points at a revision that does not exist: `current_revision` returns `None`, the
register still prints "r3", the approved record the guard exists to protect is gone, and the next
upload is allocated r3 again (`Max` is 2) — which approve then refuses as `3 <= 3`, **wedging the
document** until a second throwaway upload.
*Fix:* move both guards inside `with transaction.atomic():` after taking
`select_for_update()` on the parent document (scoped to `tenant`), and re-read
`revision.is_approved` there, mirroring approve.

**[ ] 4 — `views/DocumentKnowledgeManagement/Documents.py:229-230` `pdocument_delete` is ungated and cascades an approved chain.**
Plain `crud_delete`, no admin gate, no status condition: any workspace member can POST
`/procurement/documents/<pk>/delete/` on an `active` document and CASCADE away its entire approved
revision chain — the exact records `pdocrevision_delete:432` refuses to remove ("approved history
is never rewritten here"). The trash icon at `document/list.html:187` is offered unconditionally.
Sibling precedent: `asn_delete` (`views/OrderFulfillment/AdvancedShipmentNotice.py:239-241`,
admin-gated + status condition), and L27.
*Fix:* `@tenant_admin_required` + refuse when `current_revision_no` is non-zero; wrap the two
template buttons in the same condition.
*Rated Important not Critical:* no stated gate is bypassed — the contract specifies none, plain
`crud_delete` is the app default for 40 other entities, and the confirm text discloses the cascade.

### Minor

**[ ] 5 — `views/DocumentKnowledgeManagement/Policies.py:154,159` self-FK traversal with no tenant filter.**
`obj.superseded_by.all()[:10]` and `obj.previous_version` — precisely the hazard the `# WARNING:`
at `Policies.py:256-263` defends against 100 lines below in the same file. A foreign
`previous_version_id` would print another workspace number/title/version/status and link to it.
Every write path traced (`TenantModelForm`, `_reject_foreign`, `ProcurementPolicy.clean()`, admin
`raw_id_fields` which still runs `full_clean`) — **no route creates such a row**, so this is
defense-in-depth, not a demonstrated leak.
*Fix:* `obj.superseded_by.filter(tenant_id=obj.tenant_id)[:SUPERSEDED_BY_CAP]`.

**[ ] 6 — `templates/documentknowledge/policy/list.html:185` claims a guarantee the verb does not make.**
It says the register never shows two published versions of the same rule, but
`ppolicy_publish:265-273` only archives the predecessor reachable via `previous_version_id`.
Publish v1.0, then create v2.0 leaving `previous_version` blank and publish it: both read
"Published" for the same title. A forked chain (v2.0 and v3.0 both pointing at v1.0) does the same.
*Fix:* soften the claim here, at `policy/form.html:110` and in the `Policies.py:38-40` docstring —
or have the verb warn when `(tenant, title)` already has a published row.

**[ ] 7 — `templates/documentknowledge/revision/form.html:85` predicts the wrong revision number.**
It interpolates `document.current_revision_no|add:1`, but that is the *approved* pointer, while
`next_revision_no()` returns `Max(revision_no)+1`. With r1 approved and r2/r3 pending the page
promises r2; the upload mints r4.
*Fix:* drop the interpolated number, say "the next number in the chain".

**[ ] 8 — `templates/documentknowledge/revision/detail.html:137` inert theme modifier (L33).**
`class="btn btn-outline danger"`; theme.css has `.btn-danger` and `.btn-icon.danger:hover` but no
`.btn-outline.danger` and no bare `.danger`, so it renders completely unstyled. Every other 6.19
danger button uses `btn btn-danger`.

**[ ] 9 — `templates/documentknowledge/document/list.html:114` bare `get_full_name`, no username fallback.**
Renders an empty `<option>` for a user with blank first/last names (seeded users have names, so
smoke would not catch it). House idiom is `|default:` — 84 uses vs 20 bare across
`templates/procurement/`. **Clone family: 15 occurrences across 6 of the 12 new templates** —
find them with `grep -rn "get_full_name }}" templates/procurement/documentknowledge/`.

**[ ] 10 — `templates/documentknowledge/document/detail.html:247` offers a button the view refuses.**
"Check out" shows whenever the document is not checked out, including `status == archived`, which
`pdocument_checkout:263-266` refuses with `messages.error`.
*Fix:* wrap in a status check, matching the view computed `can_upload`.

**[ ] 11 — `views/DocumentKnowledgeManagement/Documents.py:405-408` re-index cannot make progress past 200 textless rows.**
Candidates are `extracted_text=""` ordered by id, capped at 200. A document whose current revision
genuinely has no text layer can never be filled in, so it occupies a cap slot and costs a file read
on *every* run, contradicting the docstring "picks up where it left off".
*Fix:* exclude rows whose current revision carries an `extraction_note`, or state the limitation
honestly in the docstring and success message.

### Done well

Contract adherence is exact — every view diffed against `contract-procurement-6.19.md:609-760`:
every context key, `crud_list` filter tuple, url name, template path and `Meta.fields` matches,
including the awkward ones (`approval_choices` literally `"True"/"False"` to hit `crud_list`
boolean mapping, `is_edit=False` pinned on the create-only upload page, `stats` as one conditional
aggregate). **`pdocrevision_approve` lock is genuinely correct** — same-revision, forward-order
and reverse-order interleavings all traced; the in-lock `revision_no <= locked.current_revision_no`
re-check refuses every one that would walk the pointer backwards, and the
one-atomic-block-per-attempt retry is the right idiom for reusing a transaction after
`IntegrityError`.

### Out of scope (pre-existing)

`seed_procurement.py` `handle()` ends at line 290 without printing the tenant-admin login
instructions or the `admin`-has-no-tenant warning that `seed_accounts.py:94-97` prints.

---

## Pass 2 — `explorer` (structure, consistency, duplication, spine, dead code, docstring truth)

Counts verified: 20 Python + 12 templates. **Verdict: no Critical; two Important.** Nothing here
duplicates pass 1.

### Important

**[ ] E1 — `ppolicy_delete` "Nothing cascades" becomes false the moment 6.17 lands, and the delete is ungated (L43, cross-session).**
Claimed at `views/…/Policies.py:185` (comment), `policy/detail.html:198` (to the user, in the
Danger zone) and `policy/list.html:152`. But 6.17 declares
`policy = models.ForeignKey("procurement.ProcurementPolicy", on_delete=models.CASCADE, related_name="attestations")`
at `models/RiskComplianceManagement/Policies.py:265-267`. Their CASCADE is deliberate and
documented, so the defect lands on 6.19: `ppolicy_delete` is plain `crud_delete` — no
`@tenant_admin_required`, no status guard, offered unconditionally at `policy/list.html:155` and
`policy/detail.html:199` — so any workspace member POSTing on a **published** policy silently
destroys its whole attestation ledger (signatures, `exempted_by`/`exempted_at` grants — the
compliance evidence 6.17 exists to hold), while the confirm dialog promises nothing cascades.
*Today:* `PolicyAttestation` is not yet in `models/__init__.py`, `admin.py` or any migration, so the
claim is still true and this is a landmine, not a live bug.
*Fix:* soften the three claims, and give `ppolicy_delete` the `asn_delete` treatment item 4 asks for
on `pdocument_delete` — `@tenant_admin_required` + refuse when `obj.attestations.exists()`.
**Not a duplicate of item 4** (different route, different cascade); fix in the same pass.

**[ ] E2 — "every column except `change_note` is `editable=False`" is false for `document`, and admin surfaces it.**
The revision-immutability invariant is asserted six times (`models/…/Revisions.py:18-20`,
`views/…/Revisions.py:16-17`, `forms/…/Revisions.py:21-22`, `urls/…/Revisions.py:25-27`,
`urls/…/__init__.py:24-26`, `revision/detail.html:23-24`). But `models/…/Revisions.py:78-79`
declares `document = models.ForeignKey(...)` with **no** `editable=False`, and `admin.py:817` puts
it in `raw_id_fields` while `admin.py:821-823` omits it from `readonly_fields`. The admin change
form therefore offers an editable parent FK on an existing revision. `clean()` blocks a
cross-tenant reparent; a **same-tenant** reparent is allowed and produces exactly the wedge item 3
describes — the source document pointer now names a row that is no longer its child,
`current_revision` returns `None`, the page still prints "r3", and the next upload re-allocates r3
which approve refuses as `3 <= 3`.
*Why it matters:* the `readonly_fields` tuple enumerates precisely the `editable=False` columns —
the author knew the list and did not notice `document` was missing from it. A claim repeated six
times becomes an invariant reviewers stop checking. Admin-only exposure, hence Important not
Critical.
*Fix:* add `"document"` to `ProcurementDocumentRevisionAdmin.readonly_fields`, or set
`editable=False` on the FK (no migration — `editable` is not a DB attribute) and correct the six
restatements.

### Minor

**[ ] E3 — `KnowledgeResource.is_review_due` docstring claims a stat tile that does not exist.**
`models/…/KnowledgeResources.py:255-261` says the register runs the same comparison in SQL "for its
review stat tile, so the badge on a row and the count above it always agree".
`knowledgeresource_list` aggregates `total/published/featured/used` only
(`views/…/KnowledgeResources.py:112-120`) and offers no `?review=` facet. The identical sentence on
`ProcurementPolicy.is_review_due` (`Policies.py:291-296`) **is** true, which is how the copy-paste
happened. *Fix:* delete the sentence, or add the aggregate + facet.

**[ ] E4 — one concept, three renderings, inside one sub-module.**

| surface | label | badge | facet | tile |
|---|---|---|---|---|
| `document/list.html:174`, `detail.html:63` | "Review due" | `badge-amber` | `?expiry=review_due` | no |
| `policy/list.html:137`, `detail.html:66,82` | "Review overdue" | `badge-red` | `?review=due` | yes |
| `knowledgeresource/list.html:159`, `detail.html:65,82` | "Review overdue" | `badge-amber` | no | no |

The vocabularies disagree too: `EXPIRY_FILTER_CHOICES` says "Review due"
(`models/…/Documents.py:94`), `REVIEW_CHOICES` says "Review overdue" (`views/…/Policies.py:68`).
*Cost:* a user who learns "amber = review" on one register reads red on the next and assumes worse.

**[ ] E5 — three review-date fields, two spellings, neither matching the app precedent.**
`ProcurementDocument.review_on:178`, `KnowledgeResource.review_on:194`,
`ProcurementPolicy.next_review_on:188`. The existing cross-app precedent is `next_review_date`
(`scm/…/SupplierRiskAssessments.py:45`, `procurement/…/SupplierImprovementPlans.py:126`).
*Cost:* `is_review_due` written twice and never liftable to a mixin; a future "due for review" board
special-cases the third model. *Fix:* collapse to one spelling now — costs a migration plus
`admin.py` and the policy templates; 6.17 does not reference it.

**[ ] E6 — `is_review_due` reached by two names in one sub-module.**
`ppolicy_detail:163` and `knowledgeresource_detail:165` lift the model property into context;
`pdocument_detail` does not, and `document/detail.html:63` reads `obj.is_review_due` — as do all
four list templates. The context key is pure redundancy; the document detail shape is the better
one. *Fix:* drop the key from both detail views, read `obj.is_review_due` everywhere, and amend the
contract (pass 1 verified against it).

**[ ] E7 — `KnowledgeResource.has_been_used` is dead.** `models/…/KnowledgeResources.py:263-266`.
No view, template, form, test or seeder references it; `knowledgeresource/detail.html:128` tests
`{% if obj.usage_count %}` directly, which is what the property wraps.

**[ ] E8 — the seeder justification comment contradicts the file it cites.**
`seed_procurement.py:3025-3028` says `normalize_tags`/`next_revision_no`/`file_sha256`/
`EXTRACT_MAX_CHARS` are not re-exported because of "the 6.14/6.15 rule that keeps the package
`__init__` a model registry". But `models/__init__.py` re-exports 25+ non-model callables
**including four from this sub-module** (lines 116-124/223-227), and the same seeder imports
`extract_document_text` through the package path at line 83, twenty lines above the comment. The
facts are right; the stated rule is not, and `models/__init__.py:110-115` says the opposite.
*Fix:* reword to the real reason (collision risk with `CatalogManagement` rival constants), which is
given correctly elsewhere.

**[ ] E9 — four intra-sub-module helper duplications, two with different names for identical bodies.**
`_holder_name` byte-identical in `views/…/Documents.py:245-247` and `views/…/Revisions.py:192-194`;
`_owners(tenant)` (`views/…/Documents.py:118-125`) vs `_workspace_members(tenant)` (forms ×3);
`_suppliers(tenant)` vs `_supplier_parties(tenant)`; `_need_tenant` in both view modules.
**Only `_holder_name` is a 6.19 invention** — the other three are the app-wide idiom (17 copies of
`_need_tenant`, 11 of `_supplier_parties`), so 6.19 is conforming, not diverging.
*Fix:* move `_holder_name` to `views/_helpers.py` (CLAUDE.md Backend rule 5 — used by two entities
of one sub-module). Leave the rest; fixing them app-wide is a separate job.

**[ ] E10 — `pdocument_*` vs `pdocrevision_*` spell "document" two ways.**
On the wider question: the mixed abbreviation is **within house norms** —
`supplierinvoice`/`budgetmapping` sit alongside `asn`/`rtv`/`eauc` app-wide, and the `p` prefixes
have a real justification (`document_*`/`policy_*` are namespace-generic, and `policy_list` is in
fact already claimed by 6.17). `knowledgeresource_*` being long is **not** a problem. What is a real
inconsistency is narrower: `pdocument` keeps "document" whole while `pdocrevision` clips it to
"doc", in adjacent url names of the same sub-module.
*Cost:* low, but url names are the one 6.19 surface other sub-modules hard-code. Cheap now (4 names,
4 `path()` calls, ~20 `{% url %}` tags, one `__init__.py` block); permanent later.

**[ ] E11 — unjustified function-local `import os`.** `views/…/Revisions.py:253`, inside the POST
branch. Every other function-local import in 6.19 carries an explicit reason (the
`CatalogManagement` constant collision, lazy `pdfplumber`, the not-yet-wired sub-package). `os` is
stdlib with none of those, and `models/…/Revisions.py:39` imports it at module level.

### Observations (no action)

**6.19 is the most structurally conformant sub-module in the app.** Checked against 6.13/6.14/6.15
across all four layers: no gratuitous novelty. It matched the `TEMPLATE_LIST/_DETAIL/_FORM` module
constants (26 of 81 entity view files use these; all four 6.19 modules do), `_ROW_RELATIONS` /
`_DETAIL_RELATIONS`, the one-conditional-`aggregate()` stats idiom (verbatim
`views/BudgetCostManagement/CostForecasts.py:77-79`), the `STATUS_CSS` + `status_css` pattern (22
sibling models), `TenantUniqueMixin, TenantModelForm` + `_reject_foreign`, docstring-only
sub-package `__init__.py`, the `partials/pagination.html` include, and the Danger-zone card. **All
32 views re-exported. All 55 CSS classes across the 12 templates exist in theme.css. No dead
context keys** — all 12 templates consume every key their view passes.

**Core-spine reuse is correct (L28/L29/L36).** `core.Party` via the
`roles__role__in=("supplier","vendor")` rule verbatim from 6.5/6.8; `core.OrgUnit`;
`scm.SupplierContract` + `scm.PurchaseOrder` with `Documents.py:202-203` explicitly naming the
legacy `crm.PurchaseOrder` as the wrong target; `procurement.SourcingEvent`; `accounting.Currency`
correctly exempted from the tenant re-check because it is global. All cross-app FKs by string.
**`core.Document` is genuinely untouched** — no import, no FK, no reference in any of the 20 files.
Four real FK columns over a `GenericForeignKey` is the right call for the stated reason (a GFK
cannot be `.filter(tenant=…)`d). Policy ownership resolved cleanly.

**6.19 improves on the 6.8 sibling it cloned — back-port these three.** The reminder engine
(`models/…/Documents.py:326-425`) is a deliberate structural clone of
`models/ContractsManagement/Renewals.py`. It reads `ProcurementAlert.OPEN_STATUSES` where
`Renewals.py:75` hard-codes `("open","acknowledged")`; it re-scopes the lock fetch with
`.get(pk=…, tenant=tenant)` where `Renewals.py:71` locks on pk alone; and `expiring_documents`
guards `tenant is None` where `expiring_contracts` does not.

**The alert-raise skeleton is now duplicated three times** (6.3 `run_escalations`, 6.8
`run_renewal_alerts`, 6.19 `run_document_reminders`) — ~25 lines each. Not a 6.19 defect (cloning
the proven one was right), but a fourth instance should trigger a lift to a shared
`raise_alerts_idempotent(...)`.

**6.17 has shipped a second read surface for 6.19's table** — `views/RiskComplianceManagement/
Policies.py` defines `policy_list` + `policy_detail` over `ProcurementPolicy` with its own
`_policy_qs`, `_org_units` and `SUPERSEDED_BY_CAP = 10`. Urls do not collide (`policies/` vs
`procurement-policies/`) and it correctly disclaims all authoring verbs. But once both LIVE_LINKS
blocks land, the sidebar offers two policy registers and one PPOL- row has two detail pages. Out of
6.19 scope — flagged so the second integrator decides deliberately.

**No 6.19 test suite exists** — expected, Phase 6 has not run. Noted for the test-writer.
