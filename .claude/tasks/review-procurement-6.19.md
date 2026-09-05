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
