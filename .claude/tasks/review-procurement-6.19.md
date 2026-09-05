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

# CONSOLIDATED WORKLIST — fix in this order

All six passes complete. Deduped, sorted Critical → Important → Minor, IDs assigned. The **was**
column points back at the pass section holding the full scenario, reproduction and fix.
**Runtime** = confirmed by executing it (pass 5 or 6), not merely reasoned about.

## Critical

| ID | was | Runtime | Issue |
|---|---|---|---|
| **C1** | S1 | ✅ anonymous `curl` | Every uploaded file readable with **no login, no session, no tenant**. No download view exists anywhere in the codebase; `file.url` is a raw static URL and `MEDIA_ROOT` has no tenant partitioning. `Content-Disposition: attachment` is documented in five places and **implemented in none**. *Clone family of 18 across 16 templates — fix 6.19's three links, and raise the app-wide sweep separately (L28).* |
| **C2** | P1 | ✅ measured | Revision-register dropdown selects full `ProcurementDocument` rows, unbounded, including the 200 KB `extracted_text`, to render three fields. **59.02 MB and 4.872 s at 2,007 documents** vs a 0.189 s control. Fix measured 699× smaller. |

## Important

| ID | was | Runtime | Issue |
|---|---|---|---|
| **I1** | Q1 | ✅ ×3 routes | Pointer can land on an **unapproved** revision → green **Current** badge beside **Not approved** on the same row, and delete then refuses it. `current_revision` resolves by number alone. **Fix `current_revision` to filter `is_approved=True`** as well as closing I2/I3. |
| **I2** | E2 | ✅ 2 clicks | Revision `document` FK is admin-editable (`readonly_fields` omits it) → **deterministic** route into I1, no race. Extension: with the app-wide editable `tenant`, an acme revision + file + `approved_by` stamp was moved into globex. *(The `tenant` half is app-wide — 50 of 52 ModelAdmins; only the `document` half is 6.19's.)* |
| **I3** | item 3 | ✅ | `pdocrevision_delete` guards an **unlocked** snapshot while approve uses `select_for_update` → destroys an approved revision and dangles the pointer, with a success message. *Consequence paragraph needs rewording — see pass 5.* |
| **I4** | item 2 | ✅ | Re-index blind-overwrites the search copy after a slow read → **permanently** installs a superseded revision's text. Measured: search finds the doc by superseded words, misses current ones. |
| **I5** | S2 | ✅ reachable | `classification` enforced **nowhere** — any member can search *inside*, enumerate via the facet, and read 4,000 chars of a `restricted` document. Either enforce it or stop the UI claiming "only a named few may read". |
| **I6** | item 4 | ✅ | `pdocument_delete` ungated → a non-admin cascaded **2 of 2 approved revisions**, the exact rows `pdocrevision_delete` refuses to touch. |
| **I7** | E1 | ✅ | `ppolicy_delete` ungated, and its Danger-zone text promises "Nothing cascades" — false the moment 6.17 integrates (their `PolicyAttestation` CASCADEs this table). Non-admin deleted a published policy. |
| **I8** | S4 | — | Any member can **archive a published policy** that only an admin could publish, and only an admin can repair it. Same class: `pdocument_activate`/`_supersede`/`_archive`. |
| **I9** | S3 | — | `pdfplumber` parses attacker-supplied PDFs in-process with **no page/time/memory bound**; amplified 200× by the re-index Run. "Never raises" ≠ bounded. |
| **I10** | item 1 | ✅ HTTP 500 | `ProcurementPolicyAdmin.search_fields` names `"tags"`, which the model does not have → `FieldError` 500 on any admin search. `manage.py check` does not validate `search_fields`. |
| **I11** | F1 | ✅ | "Release checkout" offered to every viewer; the view refuses non-holders. *On the same page "Upload revision" is correctly hidden — the page already knows how.* |
| **I12** | P5 | — | Re-index: **401 queries and up to 200 synchronous `pdfplumber` parses in one POST** — 200–400 s, through both the gunicorn (30 s) and nginx (60 s) timeouts. **Compose with I4 and I9 in one edit.** |
| **I13** | P4 | — | `run_document_reminders` costs 4–5 queries **per row** over a window with **no lower bound** → ~3,200 queries on a second press that writes nothing. Hoisting the dedupe drops it to **2**. |
| **I14** | P2 | ✅ measured | All four registers haul `extracted_text` they never render (465.7 KB / 6057.2 KB / 94.2 KB / 186.7 KB per page); `knowledgeresource_list` reads **no** FK at all yet `select_related`s two. |
| **I15** | P3 | ✅ 1.5 s | `?q=` sweeps the TextField **twice** per matching search (COUNT + page). Acceptable to ~1,000 docs/tenant; add the `len(q) >= 4` guard. *(A non-matching term runs it once — Paginator short-circuits.)* |
| **I16** | P6 | ✅ EXPLAIN | `(tenant, review_on)` unindexed on two hot paths → `type=ALL, rows=2021, filesort`. **Argue it from the scan, not the policy twin — that argument did not survive EXPLAIN.** |

## Minor

| ID | was | Issue |
|---|---|---|
| M1 | item 6 ✅ | `policy/list.html:185` claims the register never shows two published versions — **2, then 3, rendered on that same page**. |
| M2 | item 11 ✅ | Re-index makes no progress past 200 textless rows; contradicts "picks up where it left off". |
| M3 | item 10 ✅ | "Check out" offered on an archived document; the view refuses it. |
| M4 | F4 ✅ | Revision delete guard spelled three ways; two registers offer a trash icon the view rejects **in the I1 state**. |
| M5 | item 5 | Untenanted self-FK traversal on policy detail (defense-in-depth; no write path found). |
| M6 | item 7 | `revision/form.html:85` predicts the wrong next revision number. |
| M7 | item 8 | `btn btn-outline danger` — inert modifier, renders unstyled (L33). |
| M8 | item 9 | Bare `get_full_name` with no `\|default:` — **15 occurrences across 6 files**. |
| M9 | F2 | `revision/detail.html:128` uses `table-actions` where its three siblings use `page-actions`. |
| M10 | F3 | `<dt>`/`<dd>` outside any `<dl>` — 4 occurrences, 3 files (WCAG 1.3.1). |
| M11 | F5 | Knowledge-resource tags render as unlabelled pills; the document page labels the same thing. |
| M12 | E3 | `KnowledgeResource.is_review_due` docstring claims a stat tile that does not exist. |
| M13 | E4 | One "needs reviewing" concept, three renderings (two labels, two colours, three levels of support). |
| M14 | E5 | Three review-date fields, two spellings, neither matching the app's `next_review_date` precedent. |
| M15 | E6 | `is_review_due` reached by two names — context key on two detail views, `obj.` on the other two. |
| M16 | E7 | `KnowledgeResource.has_been_used` is dead code. |
| M17 | E8 | Seeder comment cites a re-export rule the package `__init__` contradicts in plain words. |
| M18 | E9 | `_holder_name` duplicated byte-identically across two view modules → `views/_helpers.py`. |
| M19 | E11 | Unjustified function-local `import os`; every other local import here carries a reason. |
| M20 | P7 | `prc_pdrev_tnt_doc_idx` fully redundant (leftmost prefix of the unique constraint + the FK index). |
| M21 | P8 | `pdocument_detail` spends a 5th query re-fetching a row already in memory. |
| M22 | P9 | Three uncapped reverse lists on `pdocument_detail`; the sibling bounds its fan-out at 10. |
| M23 | P11 | Seeder audit loop re-queries the seven rows it just created. |
| M24 | Q2 ✅ | `usage_count` at the `PositiveIntegerField` ceiling saturates silently; **500s under strict SQL mode**. |

## No action — recorded, deliberately not fixed

| was | Why |
|---|---|
| E10 | `pdocument_*` vs `pdocrevision_*` abbreviation — within house norms; the `p` prefixes have a real justification (`policy_list` is in fact already claimed by 6.17). |
| P10 | Pagination ordering unindexed — **app-wide pattern** (25 of 894 tenant-prefixed indexes). 6.19 conforms; fix as an app-wide pass, not a fork. |
| Q3 | Dev DB runs without `STRICT_TRANS_TABLES` — environment config, not 6.19. Means QA on this box under-reports over-range classes. |
| S5 | `supplier_visible` inert — no code path reads it. **Recorded for 6.4:** a portal view filtering it inherits I1 *and* C1. |
| — | 6.17 ships a second read surface over `ProcurementPolicy`; once both LIVE_LINKS land the sidebar offers two policy registers. Cross-session, for the second integrator. |

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

---

## Pass 3 — `frontend-reviewer` (the 12 templates)

Scope confirmed: exactly 12 files, checked against the four view modules. **Verdict: no Critical,
one Important, four Minor.** Two of pass 2's three handed-over leads do **not** survive
verification (recorded below so nobody re-files them).

### Critical

None — and the two classes that have shipped here repeatedly are both clean.
`grep -rn '{#' templates/procurement/documentknowledge/` returns **nothing**; all 12 use
`{% comment %}`. Every literal class in the 12 files was diffed against `theme.css` and **every one
exists**; the model-side maps (`Documents.py:112-123`, `Policies.py:84-88`,
`KnowledgeResources.py:116-120`) are all colour-named with a `badge-slate` `.get()` default. The
sub-module's only inert modifier is the already-filed item 8.

### Important

**[ ] F1 — `document/detail.html:242-245` offers "Release checkout" to every viewer; the view refuses most of them.**
The guard is only `{% if obj.is_checked_out %}`, but `pdocument_release`
(`views/…/Documents.py:288-296`) computes `forced = obj.checked_out_by_id != request.user.pk` and
refuses with `messages.error` when `forced and not is_admin`.
*What the user sees:* colleague A checks out DOC-00007. Every other non-admin member opening that
page sees an enabled **Release checkout** button, clicks through a confirm reading only "Release the
checkout on DOC-00007?", and gets a red banner saying they are not allowed. The holder's name is
already rendered two cards above (line 74-75), so the page has what it needs to hide the button.
*Same class as item 10, but the dominant case rather than the edge case* — item 10 needs an archived
document, this needs only a second user. Different button, view and condition; fix both together.
*Fix:* the view already computes `can_upload` for exactly this purpose — add a `can_release` sibling
key (holder-or-admin) and gate the form at line 243 on it.

### Minor

**[ ] F2 — `revision/detail.html:128` uses `class="table-actions"` for its Actions row** (pass 2's
lead, **confirmed**). `theme.css:305` is `justify-content:flex-end; gap:.25rem`; `.page-actions`
(`theme.css:248`) is `gap:.5rem` with no justify. So the revision detail's Approve/Delete/Back
buttons sit hard against the right edge with half the gap, while the same Actions card on the other
three detail pages renders left-aligned and normally spaced. *Fix:* `class="page-actions"`.

**[ ] F3 — `<dt>`/`<dd>` used outside any `<dl>` — 4 occurrences in 3 files.**
`document/detail.html:91,94` (the `<dl class="detail-grid">` opened at 68 closes at 88),
`policy/detail.html:95` (closes at 92), `knowledgeresource/detail.html:94` (closes at 85). It looks
right because `theme.css:356-357` scopes on `.detail-item dt`/`dd` rather than on the list, so
nothing visibly breaks — but a `dt`/`dd` outside a `dl` has no defined role: validators flag it and
assistive tech gets a term/definition pair with no list to attach it to (WCAG 1.3.1). Every other
`<dt>` in the sub-module is correctly nested. *Fix:* wrap each stray block in its own
`<dl class="detail-grid">`, or drop to a plain `detail-item` div.

**[ ] F4 — the revision Delete guard is spelled three different ways across three surfaces.**
`pdocrevision_delete` (`views/…/Revisions.py:432-437`) checks **two** conditions — `is_approved`
**and** `revision_no == document.current_revision_no` — and its docstring says both are deliberate
so "a pointer left dangling by any future path must not become a route to deleting the row it
points at". `revision/detail.html:129,135` mirrors both (correct); `revision/list.html:150` and
`document/detail.html:181` test only `not r.is_approved`.
Today the conditions overlap by construction so nothing is reachable — but the view deliberately
defends the dangling-pointer state that **item 3 and E2 both describe as reachable**, and in exactly
that state the two registers would offer a trash icon the view rejects.
*Fix:* add `and not r.is_current` at both sites. `is_current` reads through `r.document`, which both
views already `select_related`, so it costs no query.

**[ ] F5 — `knowledgeresource/detail.html:87-91` renders tags as unlabelled pills** where
`document/detail.html:94` labels the same thing "Tags". A reader sees a row of grey pills with
nothing saying what they are, sitting next to the `badge-muted` used for real statuses. *Fix:* give
it the same labelled `detail-item` shell as the document page (folds into F3 if taken together).

### Pass-2 leads that do NOT hold up — do not file

**"Use this renders twice on `knowledgeresource/detail.html` (:51, :147)" — not a defect, it is the
sub-module's own pattern.** Every 6.19 detail page promotes its primary verb into
`.page-header .page-actions` *and* repeats it in the Actions card: `policy/detail.html` has Publish
at :51 and :173; `document/detail.html` has Edit at :51 and :268 and Upload revision at :49 and
:121. No duplicate `id` attributes involved. Consistent — leave it.

**"`document/detail.html:247` Check out is the only POST form with no `onsubmit` confirm" — the
premise is factually wrong.** There are three unconfirmed POST forms, not one (checkout, and Use at
both :51 and :147), and the split is principled: those three are the only reversible,
non-destructive verbs in 6.19 (checkout is undone by the Release button beside it; Use increments a
counter). All 13 destructive or state-transitioning verbs — 5 deletes, 3 approves, 2 publishes, 3
archives, supersede, activate, release and both Runs — carry a confirm. A defensible rule, not an
omission. (Item 10's fix is still needed; that is about the guard, not the confirm.)

### Verified clean

**The filter contract is exact on all four registers** — the recurring defect class in this project,
and there is nothing wrong with it here. Every control maps to a real filter and every filter has a
control: document 8/8, revision 3/3, policy 5/5, knowledge resource 6/6. Both FK dropdowns use
`|stringformat:"d"` on **both sides** of the comparison; `|slugify` appears nowhere; every `<select>`
re-selects from `request.GET` after submit; every search placeholder matches its view's
`search_fields` word for word.
All 37 distinct `{% url %}` names resolve, including `procurement:event_detail`. All four registers
include `partials/pagination.html`, which replays every GET param except `page`. **No `|safe`, no
`{% autoescape off %}` anywhere** — the two grep hits are prose inside `{% comment %}` explaining
why not. All five tables wrapped in `.table-wrap`; zero raw Tailwind colour utilities, so dark mode
comes free; every icon-only button carries `title` **and** `aria-label`; every field bound with
`for="{{ field.id_for_label }}"`. `id="search"` present and unique at `document/list.html:72`,
matching `navigation.py:1678` — wired end to end. Every `colspan` matches its header count.

### Done well

**The "one constant, three surfaces" discipline is the best thing in this sub-module and should be
copied.** `SEARCH_NOTE`, `ADVISORY_NOTE`, `LIBRARY_NOTE`, `REVISION_NOTE`, `upload_note` and
`threshold_label` are each defined once in Python and printed on register, form and detail — so the
three places a user could learn what a threshold does, or what search can and cannot find inside a
PDF, are structurally incapable of disagreeing. `upload_note` is the standout: `revision/form.html:63`
prints a limit built in the view from `ALLOWED_DOC_EXTENSIONS` and `MAX_UPLOAD_BYTES`, so the page
physically cannot promise a size the form will then reject.

---

## Pass 4 — `performance-reviewer` (ORM / query efficiency)

20 Python + 12 templates + the seeder block + the 6.19 index ops in `0026_*.py:291-350`. Counts
derived statically. Sizing assumes `EXTRACT_MAX_CHARS = 200_000` with a realistic **30 KB average**
extracted text per document, 200 KB quoted as worst case. **Verdict: one Critical, five Important.**

### Critical

**[ ] P1 — `_documents()` builds the revision register's dropdown from FULL `ProcurementDocument` rows, unbounded, including the 200 KB `extracted_text` column.**
`views/…/Revisions.py:116-120` — `ProcurementDocument.objects.filter(tenant=tenant).order_by("number")`.
`revision/list.html:76-78` renders exactly three values per option (`pk`, `number`, `title`); every
other column comes down anyway, `extracted_text` and `description` included. It is **1 query** — not
an N+1, an unbounded payload that grows with the table:

| documents in workspace | bytes per load of the revision register | `<option>` elements |
|---|---|---|
| 200 | ≈ 6 MB | 200 |
| 2,000 | ≈ 60 MB | 2,000 (~120 KB of HTML) |
| 2,000 at the 200 KB ceiling | ≈ **400 MB** | 2,000 |

At 2,000 documents this is a multi-second request that can OOM a worker under concurrency, on a
primary navigation page. The sibling dropdowns (`_suppliers`/`_owners`, `_org_units`) are unbounded
too, but a `Party` or `User` row is a few hundred bytes. `ProcurementDocument` is the one model in
the app carrying a machine-written 200 KB column, and it is the one fed to a dropdown raw.
*Fix* — the app's own idiom (114 uses elsewhere, 8 in `apps/procurement`):
`.only("pk", "number", "title").order_by("number")[:200]`. Exact precedent
`apps/crm/views/DocumentContract/Contracts.py:27`. Payload 60 MB → ~12 KB, query count unchanged.
`.only()` alone is the mandatory half if the cap is unacceptable UX.

### Important

**[ ] P2 — all four registers haul `extracted_text` they never render; three join `ProcurementDocument` for nothing.**

| register | joins declared | joins the template uses | dead text per 15-row page (30 KB / 200 KB) |
|---|---|---|---|
| `pdocument_list` | supplier, owner, contract, purchase_order, sourcing_event | supplier, owner | own text **450 KB / 3 MB** + 3 unused LEFT JOINs |
| `pdocrevision_list` | document, uploaded_by, approved_by | all three | own + parent text **900 KB / 6 MB** |
| `ppolicy_list` | applies_to, owner, document, threshold_currency | applies_to, threshold_currency | parent doc text via an unread join **450 KB / 3 MB** |
| `knowledgeresource_list` | owner, document | **neither** | (15 + 6 shelf) × doc text **630 KB / 4.2 MB** |

`knowledgeresource/list.html` reads **no** FK at all (verified line by line), so its `select_related`
is pure cost. `pdocument_detail:183` has the same shape — 12 revisions = 360 KB / 2.4 MB discarded.
*Fix:* `.defer("extracted_text", …)` on each (keeps the join so a later template edit cannot
reintroduce an N+1, drops only the payload), and split `_ROW_RELATIONS` from `_DETAIL_RELATIONS` on
documents — the detail genuinely renders all five. House precedent:
`apps/crm/views/DocumentContract/DocumentVersions.py:24` `.defer("body_snapshot")`, the direct
analogue of `ProcurementDocumentRevision`.

**[ ] P3 — `?q=` sweeps the 200 KB TextField with `icontains` TWICE per request, with no minimum-length guard.**
`views/…/Documents.py:147` puts `extracted_text` in `search_fields`; `crud.py:118` applies search
before `paginate` (correct), but `Paginator` then issues `COUNT(*)` over the same filtered
queryset, so the scan runs twice.

| documents / tenant | text scanned per search (COUNT + page) |
|---|---|
| 500 × 30 KB | ≈ 30 MB |
| 2,000 × 30 KB | ≈ **120 MB** |
| 2,000 at ceiling | ≈ 800 MB |

`?q=a` matches nearly every row, so both halves do maximum work for a useless result set.
**Plainly: acceptable to roughly 1,000 documents/tenant, needs bounding beyond.** Does **not** need
FULLTEXT (the SQLite ruling stands). *Fix:* include `extracted_text` in `search_fields` only when
`len(q) >= 4`; optionally make the file-text sweep opt-in via `?in_files=1`. `SEARCH_NOTE` already
exists as the one place to explain it. (Stat tiles aggregate over `base`, not the searched qs, so
the LIKE runs twice, not three times.)

**[ ] P4 — `run_document_reminders` issues 4-5 queries PER ROW over a scan set that only grows.**
Per in-window document: SAVEPOINT + `SELECT … FOR UPDATE` + `SELECT EXISTS` dedupe + (INSERT) +
RELEASE.

| in-window documents | first press | second press (raises nothing) |
|---|---|---|
| 50 | ~252 queries | ~202 queries, **zero writes** |
| 200 | ~1,002 | ~802, zero writes |
| 800 | ~4,002 | **~3,202, zero writes** |

The scan at `:355` has **no lower bound**, so every document whose expiry or review date has ever
passed stays in the window permanently — a 3-year-old workspace with 2,000 documents and 40%
past-dated hits it. The button's confirm advertises that it is safe to press twice, so the
all-skipped path is the *common* one. Also: `expiring_documents` materialises full instances
(800 × 30 KB ≈ **24 MB resident**) and joins `supplier`/`owner`, which neither the engine nor the
view reads.
*Fix:* hoist the dedupe out of the loop into one `values_list("link_url")` set; keep the per-row
`select_for_update` only where a write will happen. Second press drops ~3,200 → **2** queries with
the concurrency guarantee unchanged. Drop the two dead joins, add `.only(...)`, and consider a floor
on the window.
*App-wide, do not fork 6.19 for it:* `ProcurementAlert` has no index reaching `link_url`; the same
dedupe shape is in 6.3 `run_escalations` and 6.8 `run_renewal_alerts`.

**[ ] P5 — re-index: 401 queries and up to 200 synchronous `pdfplumber` parses inside one POST.**
*(the item pass 1 routed here — investigated, filed with numbers)*
1 candidates query + N `current_revision` property queries + up to N UPDATEs = **up to 401**.
Wall clock is the real problem — `pdfplumber` is pure Python on pdfminer.six, ~0.1-0.3 s/page:

| per-document parse | 200-row Run |
|---|---|
| 0.15 s | 30 s |
| 1 s | **200 s** |
| 2 s | **400 s** |

gunicorn defaults to a 30 s worker timeout, nginx `proxy_read_timeout` to 60 s. **Every one of those
blows through both.** The cap is sized to "a lot of documents", not to a request budget. Saved from
Critical only because `ATOMIC_REQUESTS` is unset, so each save autocommits and a killed request
keeps finished work.
*Fix:* (a) batch the pointer resolution into one `document_id__in` query keyed
`(document_id, revision_no)`, and `bulk_update(batch_size=50)` — 401 → ~5; (b) size the cap to a
request: `REINDEX_ROW_CAP = 25` and/or a `time.monotonic()` budget with "X re-indexed, more remain".
The docstring already promises that behaviour; the code needs to keep it inside a timeout.
**Compose this with item 2's conditional `.update()` fix — same edit.**

**[ ] P6 — `review_on` is filtered on two hot paths and has no index, while its policy twin does.**
`models/…/Documents.py:216-221` declares `(tenant,status)`, `(tenant,doc_type)`,
`(tenant,expires_on)`, `(tenant,supplier)` — but not `(tenant, review_on)`, which is filtered by the
`?expiry=review_due` facet **and** by the review branch of the reminder scan. `ProcurementPolicy`
indexes exactly this pattern at `Policies.py:253`, so the asymmetry is a tell, not a choice. At
2,000 documents/tenant the facet is a full tenant scan on every hit.
*Fix:* add `models.Index(fields=["tenant","review_on"], name="prc_pdoc_tnt_review_idx")`.

### Minor

**[ ] P7 — `prc_pdrev_tnt_doc_idx` is fully redundant, on the fastest-growing table here.**
`Revisions.py:130` declares `(tenant, document)`; `:128`'s `unique_together
("tenant","document","revision_no")` already has that as its leftmost prefix, and `document` carries
Django's automatic FK index. Three structures, one access path, maintained on every INSERT of an
append-only table. `prc_pdrev_tnt_appr_idx` is a boolean at ~50% selectivity — MySQL will rarely
choose it; keep only if `?approved=` is expected to be heavily used.

**[ ] P8 — `pdocument_detail` spends a 5th query re-fetching a row it already holds.**
`:183` materialises every revision; `:196` then calls `obj.current_revision`, which runs
`self.revisions.filter(...).first()`. Replace with a `next(...)` over the list already in memory —
5 queries → 4.

**[ ] P9 — the three reverse lists on `pdocument_detail` are uncapped.** `:183-185` `list()`s
`revisions`, `policies`, `knowledge_resources` with no slice, while the sibling detail bounds its
fan-out with `SUPERSEDED_BY_CAP = 10`. A heavily-revised document is exactly the one people open.
`[:50]` + a "showing the latest 50" note matches the house pattern.

**[ ] P10 — pagination ordering is not index-supported — but this is the app-wide pattern, not a 6.19 fork.**
None of the three `Meta.ordering` tuples has a matching `(tenant, <sort key>)` index, so every page
is a filesort over the tenant's rows. App-wide only **25** of **894** tenant-prefixed index
declarations carry `(tenant, created_at)`. 6.19 conforms. If anything is added, add it to the two
tables that actually grow, as an app-wide pass.

**[ ] P11 — the seeder's audit loop re-queries rows it is holding.** `seed_procurement.py:3319-3320`
re-`list()`s the seven documents just created (and loads `description`/`extracted_text`). Cosmetic —
it runs only inside the "no documents yet" branch.

### Verified clean — with the numbers

**No N+1 in any register.** Every FK a row template touches is in that register's `select_related`.
Constant counts for a 15-row page, independent of row count: `pdocument_list` **5**,
`pdocrevision_list` **4**, `ppolicy_list` **4**, `knowledgeresource_list` **4**. Detail pages
bounded: `pdocument_detail` 5 (4 after P8), `ppolicy_detail` **2**, `knowledgeresource_detail` **1**,
`pdocrevision_detail` **1**.
**No chained `__str__` hop anywhere (L18)** — grep for a bare `{{ obj.<fk> }}` across all 12
templates returns nothing; all 39 FK reads are attribute hops. `document/detail.html:109`
deliberately prints `{{ obj.purchase_order.number }}`, never the object, so
`scm.PurchaseOrder.__str__`'s `self.vendor` hop is never triggered.
**`is_current` costs 0 queries in both places it renders** — on the register `document` is
`select_related`; on the detail Django's reverse manager populates `_known_related_objects`.
**Stat tiles are one aggregate each**, computed on the unfiltered `base`, which also keeps the
expensive LIKE out of the stats query. **Paginator's COUNT does not duplicate the `select_related`
joins** (Django strips them). No `len(qs)` anywhere; no DB work in any template loop;
`knowledgeresource_use` is a single `F()` UPDATE. **The seeder has no performance defect** —
`bulk_create` is explicitly the wrong call because `TenantNumbered.save()` allocates the numbers.

### For the test-writer — `django_assert_max_num_queries`

```
pdocument_list (30 docs)                       <= 5    # + assert page 2
pdocrevision_list (30 revs / 5 docs)           <= 4
ppolicy_list (30) / knowledgeresource_list (30, 8 featured)   <= 4
pdocument_detail (6 revs, 2 policies, 2 KRs)   <= 5    # <= 4 once P8 lands
ppolicy_detail (12 successors)                 <= 2    # assert only 10 render
knowledgeresource_detail / pdocrevision_detail <= 1
run_document_reminders (10 in-window, 1st)     <= 12   # after P4; ~52 today
run_document_reminders (2nd press, no raises)  <= 4    # after P4; ~42 today
pdocument_reindex (10 textless candidates)     <= 15   # after P5; ~21 today
```

Two payload tests a query-count assertion will **not** catch: capture each register's SQL with
`CaptureQueriesContext` and assert `"extracted_text" not in sql`; assert the revision register's
document-dropdown query carries a `LIMIT`.

---

## Pass 5 — `qa-smoke-tester` (runtime verification, report-only)

Not a route sweep — the earlier sweep already passed 37/37. This pass **executed** what passes 1-4
could only reason about. 16 mutation blocks, every one inside a rolled-back `transaction.atomic()`
with a before/after fingerprint assert; **all 16 printed "ROLLBACK VERIFIED: YES — state
identical"**. Final independent check: acme 7/6/3/4, globex identical, 0 residue rows, media
directory clean.

### Reproduced — every theorised finding CONFIRMED

**item 3** — CONFIRMED core, **REFINED consequence**. Interleaving the real approve verb into the
delete's unlocked window destroys the approved row and leaves `current_revision_no=3` with
`current_revision=None`, remaining `[1, 2]`, and a success message telling the user it worked.
Two corrections to the write-up:
- *"the register still prints r3"* is true of `document/list.html:177` only;
  `document/detail.html:72-73` prints "No approved revision yet". **The disagreement between the two
  surfaces is the visible symptom a user reports.**
- *"wedging the document until a second throwaway upload"* **does not reproduce** — and what happens
  instead is worse. See **Q1**.

**item 2** — CONFIRMED verbatim, including permanence. End state: pointer=r3, parent
`extracted_text='ALPHASUPERSEDEDTEXT r2 body'`, r3 holds the current text, row no longer a
re-index candidate. The user-visible defect measured:
`?q=ALPHASUPERSEDEDTEXT` (superseded) **finds** the document; `?q=BRAVOCURRENTTEXT` (current)
**does not**.

**E2** — CONFIRMED, and it is the **deterministic** route into the item-3 state — two admin clicks,
no race. That raises its priority relative to the race. Cross-tenant reparent is still correctly
refused, so `clean()` does its half.
**New on the same form:** `tenant` is editable too, and changing `tenant` **and** `document`
together satisfies `clean()` and relocates an acme revision — its file, its SHA-256, its
`approved_by = admin_acme` stamp — into globex, where `admin_globex` can open it, leaving acme with
a dangling pointer. **Scope honesty: `tenant`-editable is the app-wide admin pattern — 50 of 52
procurement ModelAdmins with a tenant field leave it editable**, so that half is out of 6.19's
scope. E2's stated fix (add `"document"` to `readonly_fields`) removes the reparent leg and leaves
only the app-wide `tenant` leg.

**Also confirmed by execution:** item 1 (`/admin/…/procurementpolicy/?q=abc` → **HTTP 500**,
`FieldError`, with KnowledgeResource and Document controls both 200) · item 4 (`ops_acme`, a
non-admin, deletes an active document and **cascades 2 of 2 approved revisions**) · item 6 (forked
chain → **2 published rows for one title, then 3**, rendered on the same page that claims it never
happens) · item 10 · item 11 (Run makes no progress on either press) · E1 (`ops_acme` deletes a
published policy after reading "Nothing cascades") · F1 (non-holder offered Release, refused on
click — *on the same page where "Upload revision" is correctly hidden*, which is what makes it
clearly a bug and not a style choice) · F4 (both registers offer a trash icon the view rejects).

### Measured — P1/P2/P3/P6 turned from estimates into numbers

Seeded 2,007 documents × 30 KB text (58.59 MB), rolled back. SQL captured with
`CaptureQueriesContext`, payload weighed by re-executing through a raw cursor.

| P1 — revision-register dropdown | 207 docs | 2,007 docs |
|---|---|---|
| query payload | 5.90 MB | **59.02 MB** |
| that `<select>` as HTML | 19.5 KB | **189.8 KB** of a 586.9 KB page |
| whole request | 0.19 s | **4.872 s** |

Estimates were accurate (6 MB / 60 MB predicted) and the HTML figure was **under-called by ~60 %**.
Breakdown for the fixer: only 0.810 s of the 4.87 s is the query — the rest is instantiating 2,007
model objects and rendering 2,008 `<option>` tags, so `.only()` fixes the query and instantiation
and the `[:200]` cap fixes the rendering. Control (`pdocument_list`, same 2,007 rows): **0.189 s**.
Proposed fix measured at **699× smaller**. OOM-under-concurrency remains an inference (sound: 59 MB
resident per request).

**P2** measured: `pdocument_list` 465.7 KB · `pdocrevision_list` 6057.2 KB · `ppolicy_list`
4.6 KB → **94.2 KB** once 3 policies link a fat document · `knowledgeresource_list` 7.7 KB →
**186.7 KB**. *(The seeder's documents carry almost no text, which is exactly why the first sweep
could not have seen this.)*

**P3** CONFIRMED on the doubling, **REFINED on cost**: at 2,007 docs, `?q=clause` = **1.516 s** wall,
2 LIKE passes ~0.7 s each, vs **0.189 s** unsearched. New detail: a term matching **nothing** runs
the LIKE **once** — `Paginator` short-circuits the page query at count 0. So "twice" is the common
case, not universal. The 1.5 s supports the "bound it beyond ~1,000 documents" call and no more —
the 120 MB/800 MB figures are bytes scanned, not seconds.

**P6** CONFIRMED as a plan, REFINED on argument: `EXPLAIN` gives `type=ALL, key=None, rows=2021,
Using filesort` — a genuine full scan. But it is **0.153 s at 2,007 rows** (the TEXT column is
off-page and never read for the WHERE), and the *"the policy twin has the index, so the asymmetry is
a tell"* argument **does not survive EXPLAIN** — the policy query chose the `(tenant,title,version)`
unique index, not `prc_ppol_tnt_review_idx`, and only avoids `ALL` because it has 3 rows. Add the
index; argue it from the scan, not the twin.

### New findings

**[ ] Q1 — Important — the item-3 / E2 end state is a pointer on an UNAPPROVED revision, not an unusable document.**
`models/…/Documents.py:278` (`current_revision`) and `models/…/Revisions.py:144` (`is_current`)
resolve the pointer **by number alone, with no `is_approved` predicate**. Once a dangling pointer is
re-filled by the next upload's re-allocated number, every read surface treats an unapproved file as
the document of record. Rendered proof:

```
revision-register row: r3 | Current | PDOC-00008 | ... | Not approved
revision detail badges: ['Current']
```

A green **Current** badge in one column and **Not approved** in the next, on the same row — and
`pdocrevision_delete` then refuses to remove it. The workspace's document of record, the file
`supplier_visible` would expose to a vendor portal, is one nobody approved, with no error anywhere.
Escaping requires uploading r4 and approving it, leaving the unapproved r3 permanently in history.
Reproduced three ways (item 3's race, E2's admin reparent, and directly).
*Fix:* the item-3 and E2 fixes prevent entry; **additionally make `current_revision` filter
`is_approved=True`** so no future path can paint "Current" on an unapproved row. Fold F4's
`and not r.is_current` into the same pass — same state.

**[ ] Q2 — Minor — `knowledgeresource_use` at the `usage_count` ceiling saturates silently here, 500s under strict SQL mode.**
`views/…/KnowledgeResources.py:294`. At `usage_count = 4294967295` this box returns 302, the counter
stays put, and the banner reports the unchanged number as a fresh increment. The identical UPDATE
under `sql_mode='STRICT_TRANS_TABLES'`:
`DataError: (1264, "Out of range value for column 'usage_count' at row 1")` — an uncaught 500 on a
POST verb in a strict deployment. Unreachable in practice (4.29 billion clicks); filed for
completeness and as the concrete example of Q3.

**[ ] Q3 — Observation, not a 6.19 defect — this database runs without `STRICT_TRANS_TABLES`.**
MariaDB 10.4.14, `sql_mode='NO_ZERO_IN_DATE,NO_ZERO_DATE,NO_ENGINE_SUBSTITUTION'`. Django's docs
call non-strict MySQL/MariaDB a data-corruption risk: anything the form layer misses truncates or
clamps silently instead of raising. 6.19's form layer caught everything thrown at it, so no 6.19 bug
is hidden — but **smoke and QA on this box systematically under-report over-range/over-length
classes relative to a strict production.** For whoever owns the dev-environment config; out of scope.

### States the first sweep never created — results

**Document with zero revisions: clean, nothing to file.** Swept through all eight verbs, three read
surfaces and the upload page — correct messages, correct transitions, correctly excluded from
re-index. **`?expiry=over_retention`: clean** — ORM answer and page rows agree exactly.
**Archived upload path: correct** (both GET and POST refused, 0 revisions created, 0 Upload buttons
rendered) — but Check out is still offered, confirming item 10.

### Area 5 — ~60 malformed POSTs across the four forms: **zero 500s**

Every malformed input rejected with a field-level error and no row written: over-length on every
CharField; junk and traversal strings in enums; decimals and over-range values into dates and FK
pks; `NaN` / `Infinity` / `-Infinity` / `1e400` / 17-digit / negative / 3-decimal into
`threshold_amount`, each with its own correct message; the paired amount/basis guard; **foreign-tenant
pk in all 8 FK fields — 8 for 8 rejected**; `previous_version` = itself (caught by the `__init__`
exclusion) and = its own successor (caught by the walking cycle guard, with `previous_version` left
`None` after both attempts); the upload allow-list including `a.txt.php` caught on the last segment;
21 MB refused.

**Two saves that look wrong and are not:** `is_featured="not-a-bool"` → `True` is standard Django
`CheckboxInput` semantics. Smuggled view-owned fields save with **every smuggled value ignored** —
verified end states show `status=draft`, `current_revision_no=0`, `extracted_text=''`,
`usage_count=0`, `revision_no=2` (POST said 99), `is_approved=False` (POST said True),
`tenant=acme` (POST said globex). The `Meta.fields` exclusions hold on all four forms.

**Worth recording because it looks scariest and is clean:** a file named `../../../etc/passwd.txt`
uploads and is stored as `procurement/documents/2026/09/passwd.txt` with
`original_filename='passwd.txt'`. The `os.path.basename` at `views/…/Revisions.py:256` and Django's
storage sanitisation both do their jobs. **No traversal.**

---

## Pass 6 — `security-reviewer`

*(This pass numbered its findings C1-C5; renamed **S1-S5** here to avoid colliding with the
consolidated severity IDs below.)*

### [ ] S1 — CRITICAL — every uploaded document file is readable with no login, no session, no tenant

`models/…/Revisions.py:85-88` (the `FileField`), linked from `revision/detail.html:89`,
`revision/list.html:123`, `document/detail.html:156`; served by `config/urls.py:23-24` and by Apache
from `MEDIA_ROOT` (`settings.py:127-128`).

**Runtime-confirmed with an anonymous `curl` — no cookie, no login, no tenant:**

```
GET http://localhost/NavERP/media/procurement/documents/2026/09/hvac-warranty-r1.txt
HTTP/1.1 200 OK
Server: Apache/2.4.46 (Win64) ...
Content-Type: text/plain

ROOFTOP HVAC UNIT WARRANTY - ISSUE 1
Coverage: parts and labour on both rooftop air handling units for sixty (60) months...
```

**There is no download view anywhere in this codebase** — grepping every app for `FileResponse` /
`serve(` returns only two CSV exports and an HRM letter. `file.url` is a raw static URL.
`MEDIA_ROOT` has **no tenant partitioning** (`upload_to="procurement/documents/%Y/%m/"`), so acme's
and globex's bytes share one directory with no boundary between them and none against the anonymous
internet. **The clean IDOR sweep tested the HTML pages; it never tested the object those pages
link to.**
*Path predictability:* Django appends a random suffix only on a name *collision*, so the first
upload of any filename lands at its literal sanitised name — `NDA.pdf`, `msa-signed.pdf` are one
guess. (The seeded `_GMReZp4` suffixes are the re-seeds, confirming the rule.)
**Is the `Content-Disposition: attachment` mitigation implemented or merely described? Merely
described**, in five places that read as though it were done (`Revisions.py:87` help_text,
`forms/…/Revisions.py:68-79` WARNING block, `revision/detail.html:85` "downloaded, never displayed
inside this page"). The live response carries **no `Content-Disposition` and no
`X-Content-Type-Options`** — `SECURE_CONTENT_TYPE_NOSNIFF` sits inside `if not DEBUG:`
(`settings.py:171-178`) and `.env:5` is `DEBUG=True`.
*Fix:* route every file through an authenticated, tenant-scoped `FileResponse` view with
`Content-Disposition: attachment` + `X-Content-Type-Options: nosniff`; link that url instead of
`file.url`; drop the media `static()` line from `config/urls.py`; deny direct directory access
(move `MEDIA_ROOT` outside `C:\xampp\htdocs`, or `media/.htaccess` with `Require all denied` as the
interim).
**Clone family (L28) — this is NOT 6.19-only.** `grep -rn "\.file\.url" templates/` → **18
occurrences across 16 files** (procurement RFx responses, HRM onboarding, expense claims, investment
proofs, travel bookings, inventory catalog). 6.19 is the sub-module that makes it *matter*, being
the first repository with a `confidential`/`restricted` classification and an approval chain.
*Checked and clean:* the double-extension execution vector is **not** available — XAMPP wires PHP
with an end-anchored `<FilesMatch "\.php$">`, so `evil.php.pdf` is served, not executed; `.htaccess`
is rejected because `splitext` yields `''`, not in the allow-list.
**So is the allow-list the only thing standing between this and stored XSS? Effectively yes**, and
it holds today (no `.html`/`.htm`/`.svg`/`.xhtml`/`.php`) — but it is doing that job **alone**: no
nosniff in dev, no disposition header, same-origin serving. Add one scriptable extension to that
shared set at any future point and this is stored XSS on the app origin with no second control.

### [ ] S2 — Important — `classification` is a decorative label; confidential/restricted file *contents* are searchable by every member

`views/…/Documents.py:147` (`extracted_text` in `search_fields`), `:153` (the facet), `:83`, `:176`;
`revision/detail.html:110`.
**Enforced nowhere.** Grepped `classification` across the codebase: in 6.19 it appears five times —
a model field, a badge helper, a form field, a `crud_list` filter, and a template badge. **Not one
queryset, decorator, permission check or `if` anywhere in `apps/` reads it to decide access.**
`restricted` — documented at `models/…/Documents.py:79` as "the tier above confidential, for records
only a named few may read" — grants and restricts nothing.
*Attack:* a junior buyer with an ordinary login GETs `/procurement/documents/?q=indemnity+cap`;
`apply_search` ORs `extracted_text__icontains`, matching the **body text** of a `restricted`
document (the seeder creates both a confidential and a restricted one, so this is reachable on a
stock install). The row leaks number, title, supplier, owner, dates. Two clicks further,
`pdocument_detail` applies no check and `revision/detail.html:110` renders
`{{ obj.extracted_text|truncatechars:4000 }}` — 4,000 characters of the restricted file. And
`?classification=restricted` is offered as a **facet**, so the UI hands over an enumeration of
exactly the need-to-know set. Even without reading the body, the search oracle alone confirms the
presence and wording of a suspected phrase.
*Fix:* enforce it once in `_document_qs` and every fetch (owner-or-admin for
confidential/restricted), mirrored on the revision side via `document__classification`. **If a full
read-ACL is genuinely deferred to Module 13.7, then say so on the form help_text and the detail
badge** — the current UI, with a tier literally named "for records only a named few may read",
actively misleads the person choosing it.

### [ ] S3 — Important — `pdfplumber` parses attacker-supplied files in-process with no page, time or memory bound

`models/…/Revisions.py:271-285`, driven from the upload (`views/…/Revisions.py:296`) and re-index
(`views/…/Documents.py:420`). Any authenticated member (upload is `@login_required` only) can post a
20 MB PDF — inside `MAX_UPLOAD_BYTES` — crafted with a huge page count or deeply nested streams.
`text = "\n".join(page.extract_text() … for page in pdf.pages)` materialises the whole joined string
**before** the `EXTRACT_MAX_CHARS` truncation at :285, and `pdf.pages` retains every page object.
The `except Exception` at :281 is honest about not raising (`MemoryError`/`RecursionError` are both
caught) — but **"never raises" is not "bounded"**: the worker has already spent the CPU and RSS,
synchronously, inside the request. No `signal`, `alarm`, timeout, page cap or `resource` limit
anywhere in the module. Amplified 200× by `pdocument_reindex` (`REINDEX_ROW_CAP = 200`) — 200
planted bombs are one request. The plain-text branch **is** bounded correctly
(`Revisions.py:261` reads a fixed `EXTRACT_MAX_CHARS * 4` prefix); the gap is PDF-only.
*Fix:* cap pages (`MAX_EXTRACT_PAGES = 500`), accumulate and `break` once the character budget is
met, call `page.flush_cache()` per page, and move extraction off the request path (or wrap a hard
wall-clock budget) before this accepts untrusted uploads. Compose with P5.

### [ ] S4 — Important — any member can archive a published policy that only an admin could publish

`views/…/Policies.py:302-304` (`ppolicy_archive`: `@login_required` + `@require_POST` only) against
`:204-207` (`ppolicy_publish`: `@tenant_admin_required`). A non-admin POSTs
`/procurement/policies/<pk>/archive/` on the workspace's published bidding policy; no status guard
applies, and the rule vanishes from the published library for everyone. **They cannot undo it** —
`ppolicy_publish:238-242` refuses to re-publish an archived row, so restoring the workspace's stated
position needs an admin to author a new version. One click, member-reachable, admin-to-repair,
changing what every member sees as authoritative.
The docstring's defence ("taking a rule OUT is the safe direction") does not survive the asymmetry:
if publish needs an admin because it makes a rule the workspace's stated position, un-making that
position needs the same gate.
*Fix:* `@tenant_admin_required` on `ppolicy_archive` + gate the button. **Same shape, lower impact:**
`pdocument_activate` / `_supersede` / `_archive` (`Documents.py:311,329,354`) are all
member-reachable and all change the document-of-record's status (archiving additionally blocks
checkout and new revisions). Worth a deliberate ruling rather than a default.

### [ ] S5 — Minor — `supplier_visible` is inert today

Asked directly, answered directly: **no code path acts on it.** Every hit is passive — model field,
form checkbox, admin `list_filter`, seeder value, display badge, one docstring. No queryset filters
on it; no view reads it.
*Recorded for whoever ships 6.4:* the moment a vendor-portal view filters `supplier_visible=True`,
it inherits **Q1** (the pointer can land on an unapproved revision) **and S1** (the file is
anonymously readable regardless of the flag), and this checkbox becomes the switch that publishes an
unapproved internal file to an external counterparty. That portal view must filter
`supplier_visible=True` **and** join through to an `is_approved=True` current revision, **and** serve
bytes through the S1 download view, never `file.url`.

### Authorization matrix (all 32 views)

| Gate | Count | Views |
|---|---|---|
| `@tenant_admin_required` | **3** | `pdocument_reindex`, `pdocrevision_approve`, `ppolicy_publish` |
| `@login_required` only | **29** | everything else |

The three admin gates are the right three, correctly placed — approval decides the document of
record, publish decides the stated rule, re-index reads every stored file and rewrites a searched
column. **The split is defensible on the forward verbs and indefensible on the inverse ones**: S4 is
the clear break, with `pdocument_archive`/`_supersede`/`_activate` in the same class.
`pdocument_checkout`/`release` are correct as-is — an advisory lock, and forced release already
requires holder-or-admin with `forced` recorded in the audit row.
`knowledgeresource_publish`/`archive`/`use` are defensibly ungated: the resource states no binding
rule and retires nothing, and `use` increments a counter documented as a click tally.

### Clean — checked, nothing to report

**CSRF:** 30 `method="post"` forms across the 12 templates, 30 `{% csrf_token %}`, one-for-one; no
`@csrf_exempt`. **XSS:** zero `|safe`, `mark_safe`, `{% autoescape off %}`, inline handlers, `eval` —
the only string matches are two comments *forbidding* them. No user data in an inline `style`
(L26). **Open redirect:** every `redirect()` targets a reversed url name with a pk; no `?next=`;
`knowledgeresource_use` deliberately redirects to its own detail page rather than `file.url` and
documents why — **that mitigation is implemented.** **SQLi:** no `.raw()`, `.extra()` or
`cursor.execute`; `apply_search` builds ORM `Q` objects from a hard-coded field tuple with `q` as a
parameter. **Upload validation:** extension + size checked against the core constants, imported
function-locally for the stated (correct) reason; no SVG in the allow-list. **SHA-256:** streams
chunks with both `seek(0)` calls present; the WARNING correctly calls it a checksum, not
tamper-proofing. **Mass assignment:** both `Meta.fields` sets exclude every machine-written column,
which are additionally `editable=False`. **Audit:** all eleven verbs call `write_audit_log`, with
`sha256` truncated to 16 chars. **Secrets:** none in the sub-module; no generated value in a
`messages.success` (L25).
