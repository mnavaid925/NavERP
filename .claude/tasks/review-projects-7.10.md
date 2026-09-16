# Review — Projects 7.10 Document & Knowledge Management

Six read-only lanes ran **serially** (code-reviewer → explorer → frontend-reviewer →
performance-reviewer → qa-smoke-tester → security-reviewer) over the 7.10 file set.

**BASE** = `d8bcee2c7798f8edebfa1e434271a51bbb459a7e` (the interrupted session's last commit — the
`LIVE_LINKS["7.10"]` entry).
**HEAD at review time** = `a10909ae` (31 commits: 4 backend fixes + the seeder + 22 templates + 4 docs).

## Scope — and why this review is shaped differently from 7.1–7.9

**The backend was NOT written by this session.** A previous session committed the whole 7.10 backend
(models / forms / views / urls / admin / migration `0014` / `LIVE_LINKS["7.10"]`) and then died while
writing templates: **1 of 22 templates** existed, `0014` had **never been applied**, and the seeder had
no 7.10 block — while the sidebar advertised the sub-module as **Live**. This session adopted that
work, finished it, and in doing so found four defects in the already-committed backend.

So the lanes are reviewing **two** things at once, and both matter:

1. **The backend as it now stands** (5 models, 7 url modules, 5 forms, 7 view modules, admin, seeder,
   `LIVE_LINKS`), including the four fixes below — sanity-check the fixes rather than re-reporting
   them.
2. **The 22 templates**, which are new in this session and have had no review at all.

**Scope is pinned by the file set, not by a bare commit range** — but unlike 7.1–7.9 no peer session
is live in this checkout (verified: the working tree was clean at `d8bcee2c` apart from untracked
`.workbuddy-ai/`, `.zcode/` and the stray `$t/`), so `d8bcee2c..HEAD` is a legitimate range here.

Files under review:

- `apps/projects/models/DocumentKnowledgeManagement/{ProjectFolders,Documents,Revisions,Templates,Knowledge}.py`
- `apps/projects/forms/DocumentKnowledgeManagement/{ProjectFolders,Documents,Revisions,Templates,Knowledge}.py`
- `apps/projects/views/DocumentKnowledgeManagement/{ProjectFolders,Documents,Revisions,Templates,Knowledge,RepositoryOverview,RetentionBoard}.py`
- `apps/projects/urls/DocumentKnowledgeManagement/*.py` + the `apps/projects/urls/__init__.py` wiring
- `apps/projects/admin.py` (the 7.10 block), `apps/projects/management/commands/seed_projects.py`
  (`_docmgt` + `--flush` ordering + imports), `apps/core/navigation.py` (`LIVE_LINKS["7.10"]`)
- `templates/projects/documentknowledge/**` (22 files)
- migration `0014_projectfolder_projectdocument_documenttemplate_and_more`
- `.claude/tasks/todo.md` §"Projects 7.10 — Document & Knowledge Management (build plan)" is the
  frozen spec (there is no `contract-projects-7.10.md` — the plan section IS the contract).

## Build-phase context for the lanes

- **Smoke gate** (`temp/smoke_710.py`): **167 checks, 0 failures**. Renders every 7.10 route with
  CONTENT assertions, asserts the 14 POST-only verbs answer GET with **405**, exercises the verb state
  machines in both directions (checkout → second checkout refused → checkin; approve → pointer moves →
  re-approve refused; archive refused under hold; delete refused under hold; `kne_use` counter),
  verifies the retention **Run is idempotent** from a clean slate, walks page 2 and an out-of-range
  page on all five paginated registers, throws **31 junk/empty lenses** at them (L11/L35), probes an
  **empty tenant**, and checks **20 cross-tenant IDOR probes → 404 for both actors** plus 8 anonymous
  → login redirects and no `{#` / `{% comment` leaks.
- **Test suite**: the full `apps/projects` suite is **3270 passed / 0 failed / 2 skipped** (from
  `--junitxml`, not stdout). ⚠️ **There is no `docmgt_*` lane yet** — 7.10 is covered by the smoke
  script and by the four existing lanes continuing to pass, NOT by a lane of its own. That is the
  outstanding close-out work; do not read the green suite as 7.10 being tested.
- **Four defects were found and fixed during the build, before any lane ran.** They are committed and
  the smoke is green against the fixes. Lanes should **sanity-check** them, not re-report them:
  - **F-1 (`a0db8441`)** — `pdm_list` applied **only `?q=`**. It passed `projects`, `folders`, four
    choice tuples and `owners` into the context and rendered a **seven-select filter bar** that
    filtered nothing. It now hands the whole `filters` spec to `crud_list` (where the L11 guards
    live) with `search_fields=[]`, which keeps its own 4+-character `_search()` as the only search.
  - **F-2 (`4ee7b166`)** — `kne_search` raised **`NameError: name 'Q' is not defined` on every
    non-empty `?q=`**; `Q` was never imported and `views/_common.py` star-exports no `Q`/`F`. A hard
    500 on the sub-module's own search page, with the empty page returning 200 — so it looked fine.
  - **F-3 (`3a83f0bb`)** — `ProjectDocumentForm` left **`project` editable** on an existing instance
    while narrowing `folder`/`milestone`/`task` from `self.instance.project_id` (the OLD project), so
    changing the project left every folder failing "Select a valid choice" with no way to recover.
    The field is now `disabled` on edit, which is what the form's own docstring already claimed.
  - **F-4 (`3b7859e2`, pre-existing 7.9 defect, NOT 7.10)** — `_cc_activityfeed` was imported into
    `apps/projects/urls/__init__.py` but **never concatenated into `urlpatterns`**, so
    `projects:activity_feed` raised `NoReverseMatch` and took `/projects/` (the module landing page,
    which every 7.10 breadcrumb hangs off) down with it. Measured before/after: reverting the one-line
    fix leaves 7.9's own `test_collab_security.py::test_collab_anonymous_is_redirected_to_login[activity_feed-None]`
    **failing on `main`**; with the fix it passes. Flagged so the security lane can confirm the fix
    is complete rather than assuming a 7.9 defect is out of scope.
- **Deliberate boundary rulings the lanes should test against, not re-litigate** (each is stated in
  the model/view docstrings and in the todo.md plan):
  - **`core.Document` is NOT touched** — no import, no FK, no migration. `ProjectDocument` is 7.10's
    own row with real link FKs. 7.9's `DocumentShare` (which DOES FK `core.Document`) is shown on the
    document detail page as a **read-only lens**. Do not file "7.10 should reuse core.Document".
  - **Retention is a documented INTENT plus verbs.** Nothing in 7.10 deletes anything on a schedule;
    enforcement / immutable vault / proof-of-deletion are 13.9/13.14's. No page may claim otherwise.
  - **The check-out lock is cooperative and in-app**, not an OS file lock. Check-in is open to any
    member on purpose (a stale lock must not deadlock a document).
  - **`is_format_locked` is an intent**; nothing enforces authorship or formatting (13.1's).
  - **`usage_count` is a click counter** (atomic `F()+1`), not a metric and not an audit trail;
    **`is_featured` is a shelf, never a permission**.
  - **Content-only standards live in `KnowledgeEntry.kind="template"/"standard"`**, not in
    `DocumentTemplate` (file-backed only) — deliberately two lenses.
  - **There is no `docmgt` revision edit path by design** — no edit url, view or template; immutability
    is structural (everything but `change_note` is `editable=False`).
  - **`ProjectDocument.title` is `blank=False`**, so the model's `clean()` branch allowing a blank
    title while `status == "expected"` is **unreachable**. This is already recorded in the SKILL.md as
    a known inconsistency for the close-out — the lanes should decide it one way or the other rather
    than each re-discovering it.
- **Seeded shape (both tenants):** 12 folders (10 on the active project incl. an archived branch, 2 on
  the second) · 22 documents (one `expected` placeholder, one checked out, one under legal hold, two
  archived, one superseded, two with a closed retention window) · 23 revisions (two superseded pairs,
  four left pending approval) · 16 standards · 17 knowledge entries (three featured). The document and
  knowledge registers both clear the 15-row page.
- **Known seeder constraint:** `backdate()` exists because `retain_until` is
  `created_at + 30 * retention_months`; without ageing a seeded row no document could ever be
  retention-due and the retention board's headline figure would be structurally zero. `created_at` is
  `auto_now_add`, so a queryset `.update()` is the only honest way to give a seeded row a past.

---

## Lane findings (raw, appended per lane)

### Lane 1 — code-reviewer (serial pass 1)

**Scope check.** Read in full: all 5 model modules (`models/DocumentKnowledgeManagement/{ProjectFolders,Documents,Revisions,Templates,Knowledge}.py`), all 5 form modules, all 7 view modules, all 8 url modules + the 7.10 wiring in `apps/projects/urls/__init__.py` (imports 63-69, concatenation 156-162), the 7.10 admin block (`admin.py:524-588`), `_docmgt` + the `--flush` block + imports in `seed_projects.py` (lines 285-296, 2291-2824), `LIVE_LINKS["7.10"]` (`navigation.py:1859-1879`), migration `0014`, and all 22 templates under `templates/projects/documentknowledge/**`. Read for context: `apps/core/crud.py`, `apps/core/utils.py` (`write_audit_log`), `apps/core/models/AuditLog.py`, `apps/core/forms/_common.py` (`TenantModelForm`), `apps/projects/models/_base.py`, `forms/_common.py`, `views/_common.py`, `views/_helpers.py`, `templates/partials/pagination.html`, and the todo.md plan section (lines 7987-8324). Read-only probes run: `extract_text()` on a raw `UploadedFile`, the L10 filter-argument render, `Paginator.get_page().window` vs `crud.paginate().window`, a programmatic set-difference of all 45 `projects:*` names used by the templates against the URLconf, `makemigrations --check --dry-run`, and MySQL `sql_mode`/column-width inspection. **I cannot verify runtime behaviour** — no request was served, no row written; every rendering/crash claim below is a template-engine or Python-level reproduction, and lane 5 owns the end-to-end pass.

**Sanity-checks of the four already-fixed defects**

- **F-1 — PASS.** `pdm_list` hands the whole 7-tuple `filters` spec to `crud_list` with `search_fields=[]`, and its own `_search()` runs before it: `views/DocumentKnowledgeManagement/Documents.py:54,60-75`; `crud_list` applies every filter before `paginate()` (`core/crud.py:119-165`).
- **F-2 — PASS.** `Q` is imported: `views/DocumentKnowledgeManagement/Knowledge.py:12` (`from django.db.models import F, Q`), used at `:53-56`.
- **F-3 — PASS.** `self.fields["project"].disabled = True` inside the `if self.instance and self.instance.pk:` branch: `forms/DocumentKnowledgeManagement/Documents.py:56-63`; the three narrowed FK querysets at `:50-54` are narrowed from the instance's project, matching the docstring.
- **F-4 — PASS.** `_cc_activityfeed` is imported at `urls/__init__.py:57` **and** concatenated at `:145`; `reverse("projects:activity_feed")` → `/projects/activity-feed/` (probe). The 7.10 clone shape is *not* repeated: all seven `_dk_*` modules are concatenated (`urls/__init__.py:156-162`).

**Coverage — clean categories (no findings filed)**

- **Multi-tenancy (§2):** every 7.10 queryset filters `tenant=request.tenant` or scopes through a tenant-verified parent (`obj.revisions`, `ProjectDocument.objects.filter(tenant=…, folder=obj)`, `_decorate`'s grouped count); no `objects.all()`, no pk-only `.get()`. Every FK dropdown is tenant-scoped by `TenantModelForm` (`core/forms/_common.py:52-55`) **and** re-checked by `_reject_foreign`; each model carries an `_id`-first cross-tenant backstop in `clean()`. No new model is missing a tenant FK; every `unique_together` includes `tenant`.
- **Authorization (§3):** all 40 views are `@login_required` (grep: 11/8/6/1/2/6/6 = 40; no public endpoint in 7.10); all 14 POST-only verbs carry `@require_POST` (matches the smoke's 14 × 405); the 4 delete views delete only on POST; every delete/archive/hold refusal is server-side, not template-only.
- **URL wiring:** all 45 `projects:*` names the 22 templates reverse exist (programmatic set-difference = ∅), incl. `mst_detail`, `tsk_detail`, `dsh_list`, `overview`; literal routes precede `<int:pk>` in all 7 modules; the 7.10 first segments (`documents/`, `doc-folders/`, `document-revisions/`, `document-templates/`, `knowledge/`, `document-repository/`, `document-retention/`) are disjoint.
- **Migrations (§7):** `0014` matches the models field-for-field (PROTECT on `ProjectDocument.folder`, all 10 indexes, all `unique_together`, `editable=False`/null/default); `makemigrations --check --dry-run` → "No changes detected". No destructive operation.
- **Package structure (§5):** one `<Entity>.py` per entity in all four layers, absolute imports, re-export blocks complete (`models/__init__.py:117-121`, `forms/__init__.py:130-134`, `views/__init__.py:383-432`); sub-package `__init__.py` files empty by house convention; template paths `templates/projects/documentknowledge/<entity>/<page>.html` — no flat `*_<page>.html`, no `*_advanced.py`.
- **CRUD/filter contract (§6):** list pages apply search + filters before pagination; context carries `status_choices`/`kind_choices`/`category_choices`/`doc_type_choices`/`classification_choices` + tenant-scoped `projects`/`folders`/`owners`/`documents`; pk filters use `|stringformat:"d"`, never `|slugify`; every list has view/edit/delete actions with csrf+confirm; every detail page has a Back-to-List.
- **Templates (§9):** all extend `base.html`; badge classes are colour-named only (no `-success`/`-danger`); every POST form has `{% csrf_token %}`; **no `{#` comment exists anywhere in the 22 files**, so no multi-line leak; status badges read the exact CHOICES values (`'published'`, `'retention'`, `'archived'`) with display fallbacks; `partials/pagination.html` is L9-guarded and preserves GET params.
- **Data integrity (§8):** `pdv_approve` re-checks the pointer inside `select_for_update`; `revision_no` is allocated inside the same transaction; `kne_use` uses `F("usage_count")+1`; forms exclude `tenant`/`number`/stamps/verb-written state; `--flush` deletes revisions → documents → folders (correct PROTECT/CASCADE order); `_docmgt` is guarded per tenant and dispatched after `_collab`, mints `ContentFile` only inside the guard's `else`, and uses `.txt` payloads so extraction genuinely runs; every verb writes an `AuditLog` row with the verb in `changes` (except L1-C2).
- **Spine reuse (§4) / simplicity (§11):** no new customer/vendor/employee table, no second ledger, no stored balance; `core.Document` untouched (no import/FK/migration); no debug prints or dead blocks outside L1-M1.

**Findings**

**L1-C1 — Critical — `apps/projects/views/DocumentKnowledgeManagement/Revisions.py:55`**
`pdv_upload` calls `extract_text(uploaded)` on the **raw `UploadedFile`** *before* `revision.save()`. `extract_text` reads `stored_file.path` (`models/DocumentKnowledgeManagement/Revisions.py:192-197`); a plain `UploadedFile` has no `.path`, the defensive `except Exception` swallows the `AttributeError`, and the function returns `("", NOTE_UNREADABLE_PATH)` — verified by probe: `extract_text(SimpleUploadedFile("probe.txt", b"…"))` → `('', 'The stored file could not be reached on disk.')`. So every revision uploaded through the UI stores `extracted_text=""` plus a **false** note, and `pdv_approve` then copies that `""` over the parent's search copy (`Revisions.py:97`).
*Why it matters:* Ruling 6's denormalized full-text search never matches anything uploaded through the only UI path that creates revisions — and because `pdv_approve` **overwrites** the parent's `extracted_text` rather than merging, approving a UI-uploaded revision silently destroys text an earlier approval or a re-index had put there. The history panel and the compare page then display "The stored file could not be reached on disk", blaming the file for a bug in the caller. It is recoverable per document via `pdm_reindex` (which correctly reads `current.file`), which is why I grade it Critical-with-recovery rather than unrecoverable data loss — but no test covers it: all 46 revisions in the DB are the seeder's (23 × 2 tenants), and 0 carry the unreadable note, so the smoke's `pdv_upload` POST never created a row.
*Fix:* mirror the seeder's proven order (`seed_projects.py:2434-2438`) — `revision.save()`, then `text, note = extract_text(revision.file)`, then `revision.save(update_fields=["extracted_text", "extraction_note"])` — inside the same `transaction.atomic()`.

**L1-C2 — Critical — `apps/projects/views/DocumentKnowledgeManagement/RetentionBoard.py:112`**
`write_audit_log(request.user, None, "retention_reminders_run", {...})` passes a **23-character** action. `core.AuditLog.action` is `CharField(max_length=10, choices=ACTION_CHOICES)` where the choices are only `create`/`update`/`delete` (`apps/core/models/AuditLog.py:8,16`), and `views/_common.py:10-13` states the app-wide rule that every action string is ≤ 10 chars with the verb in `changes`. This checkout's MySQL runs `sql_mode=NO_ZERO_IN_DATE,NO_ZERO_DATE,NO_ENGINE_SUBSTITUTION` — **no `STRICT_TRANS_TABLES`** — so the value is silently truncated to `retention_` (`.create()` skips choice validation, so nothing raises here); on a strict-mode MySQL/MariaDB (the production default) the same insert raises `DataError` and 500s the retention Run.
*Why it matters:* the audit row for the retention Run is corrupt/meaningless on this checkout and the Run is a 500 on a strict server — the exact mainline button the retention board is built around. A repo-wide grep for other over-length actions returns nothing, so this is the only instance of the shape.
*Fix:* `write_audit_log(request.user, None, "update", {"verb": "retention_reminders_run", "raised": raised, "skipped_open": skipped})`.

**L1-I1 — Important — `apps/projects/views/DocumentKnowledgeManagement/Revisions.py:130-136`**
`pdv_restore` builds the new revision without `checksum` (the field defaults to `""`), even though the file is copied by reference from the source revision and the view's own docstring (`:116`) promises "its own number, **its own checksum** and its own change note".
*Why it matters:* restored rows render no `sha256` in the history panel (`projectdocument/detail.html:167`) and `pdv_compare`'s `same_checksum` is `False`, so `projectdocumentrevision/compare.html:20` prints "Different bytes" — and `:82` explicitly tells the reader "A restore forward produces exactly this" — for a restore that is byte-identical. The one thing the checksum exists for ("same file?" answerable without reading either one) is unavailable on the one verb whose whole point is re-using an existing file.
*Fix:* pass `checksum=revision.checksum` in the constructor at `:130-135`.

**L1-I2 — Important — `templates/projects/documentknowledge/projectdocument/detail.html:21`**
`{{ current.approved_by.get_full_name|default:current.approved_by.email|default:"&mdash;" }}` is guarded only by `{% if current %}`, but `approved_by` is `SET_NULL` (`models/…/Revisions.py:72-74`), so it is `None` once the approving user is deleted. A `None` FK inside a filter **argument** raises: reproduced with the template engine — `VariableDoesNotExist: Failed lookup for key [email] in None`.
*Why it matters:* a latent 500 on the document detail page (L10), the page every 7.10 breadcrumb and the whole revision chain hang off. It is latent in seeded data (an approver always exists), so it needs a user deletion to fire — but the fix is one guard and this is the only unguarded instance in the 22 templates (all 22 other `get_full_name|default:…` sites are wrapped in `{% if fk %}`).
*Fix:* wrap the value in `{% if current.approved_by %}…{% else %}&mdash;{% endif %}` and drop the second `|default:`.

**L1-I3 — Important — `apps/projects/views/DocumentKnowledgeManagement/Knowledge.py:68,77-80`**
`kne_search` paginates with its own `_page()` (`Paginator(qs, size).get_page(...)`) instead of `crud.paginate()`, and `crud.paginate` is the only thing that sets `page.window` (`core/crud.py:26-33`). Verified: `Paginator.get_page()` has no `window`; `crud.paginate()` has `[1, 2, 3]`. `templates/partials/pagination.html:16` iterates `page_obj.window`, and `ForNode` resolves a missing attribute with `ignore_failures=True`, so it renders **nothing** — no error, no numbered links.
*Why it matters:* the knowledge search page silently loses its page-number window and offers only Prev/Next, unlike every other register in the app — a view/template context mismatch on the sub-module's own search page, invisible on one page of results. I'm unsure between Important and Minor because it degrades rather than crashes; I picked the higher level per the rubric.
*Fix:* `from apps.core.crud import paginate` and use `paginate(request, qs)` in `_page()`, or set `page.window` in place.

**L1-I4 — Important — `templates/projects/documentknowledge/projectdocument/detail.html:66`**
`{% if obj.extraction_note %}Last extraction note: {{ obj.extraction_note }}{% endif %}` reads a field that does not exist on `ProjectDocument` — `extraction_note` lives on `ProjectDocumentRevision` (verified: `hasattr(ProjectDocument, "extraction_note")` is `False`; the attribute is absent from `models/…/Documents.py`).
*Why it matters:* the `{% if %}` is permanently `False`, so the line is dead markup and the only place a failed text read would surface to a user never renders. This is the L7 class the checklist names first ("a mismatch renders silently empty"), and it compounds L1-C1: the false note is stored but never shown where it was meant to be.
*Fix:* read it off the current revision — `{% if current.extraction_note %}…{{ current.extraction_note }}{% endif %}` — or drop the line.

**L1-M1 — Minor — `apps/projects/models/DocumentKnowledgeManagement/Documents.py:146-152`**
`LIVE_STATUSES`, the `OPEN_STATUSES` alias and the `is_live` property have no reader anywhere in the app (grep: definitions only), yet the comment asserts "The register's default lens and the retention board both read this rather than repeating the tuple". Neither does: `pdm_list` applies no status lens, and `doc_retention` filters `is_archived=False` in Python (`RetentionBoard.py:42`) and counts `figures["live"]` from `is_archived=False` (`:65`).
*Why it matters:* dead code plus a comment that asserts a contract nobody implements — a future reader will trust the comment and "reuse" the tuple instead of re-checking. *Fix:* delete the three names, or make the retention board's `live` figure and a register default lens actually use them.

**L1-M2 — Minor — `templates/projects/documentknowledge/projectdocument/list.html:72`**
The empty value of the archive lens is labelled **"Live register"**, but the view's `("archived", "is_archived", False)` filter is skipped when the value is empty (`Documents.py:66`), so the default lens applies **no** `is_archived` filter and the list includes archived rows under a "Live register" label.
*Why it matters:* the filter bar tells the user they are looking at the live register while two archived documents are in the table. *Fix:* relabel to "Any state", or implement the live default (which is what L1-M1's tuple was for) and add an explicit "Archived only" lens.

**L1-M3 — Minor — `apps/projects/models/DocumentKnowledgeManagement/Revisions.py:19-21`**
The docstring says "7.10 refuses an upload while the parent is checked out (`models.Documents.clean()` is the guard)". No such guard exists in `ProjectDocument.clean()` (`Documents.py:292-324`) nor in `ProjectDocumentRevision.clean()` (`Revisions.py:115-135`); the only implementation is `forms/DocumentKnowledgeManagement/Revisions.py:51-56`, and `revision.save()` in the view never calls `full_clean()`.
*Why it matters:* a maintainer following the pointer will believe the model layer enforces the lock; there is no reachable bypass today (the only upload path runs the form), but the model is not the boundary the comment claims. *Fix:* correct the cross-reference, or move the check into `ProjectDocumentRevision.clean()` as the plan's Model-2 bullet specifies.

**L1-M4 — Minor — `apps/projects/forms/DocumentKnowledgeManagement/Templates.py:30-38`** (with `models/…/Templates.py:59`)
`clean_file` returns early when no file is posted, with no create/edit distinction, so a **fileless** standard can be created — and the model field is `blank=True, null=True`. This contradicts both the plan's Model-4 bullet ("file is required on create, optional on edit") and the boundary ruling the header pins (content-only standards belong in `KnowledgeEntry.kind="template"/"standard"`, `DocumentTemplate` being file-backed only); the list template's own help text (`documenttemplate/form.html:30`) invites the prose row, and `_docmgt` ships **8 of its 16 standards without a file** (`seed_projects.py:2663,2669,2676,2683,2694,2696,2703,2706`).
*Why it matters:* the "deliberately two lenses, never two near-duplicate tables" boundary is not enforced anywhere, so the same "how we write a charter" content can sit in both registers. *Fix:* require the file on create in `clean_file` (and/or flip the model to `blank=False`), and either give those 8 seeded rows files or move them to `KnowledgeEntry`.

**L1-M5 — Minor — `apps/projects/forms/DocumentKnowledgeManagement/ProjectFolders.py:43-45`**
On edit the `parent` queryset excludes only `self.instance.pk`, not its descendants, although the plan's Model-1 bullet pins "on edit, excludes self + descendants".
*Why it matters:* the edit form offers a descendant as a parent and the user only learns it is wrong after submitting ("That would move the folder inside its own subtree", from the model's `clean()` via `_post_clean`) — a confusing round trip, not a hole, because the model refuses it. *Fix:* reuse `ProjectFolder._is_descendant_of` / `ancestor_chain` to exclude the subtree from the queryset.

**L1-M6 — Minor — `apps/projects/admin.py:544-546`**
`ProjectDocumentAdmin.readonly_fields` locks the pointer, the search copy, the lock and the hold "because an admin edit would forge the one thing the register exists to attest" — but omits `is_archived`, which `models/…/Documents.py:193` declares "VERB-WRITTEN by `pdm_archive` (a Toggle) ONLY". `ProjectFolderAdmin` (`:531`) has the same gap.
*Why it matters:* a superuser can flip `is_archived` from admin with no `archived_at`/`archived_by` (both `editable=False`, so auto-excluded) and no status sync, leaving a row whose archive badge, the register's archive lens and the retention board's "archived" figure disagree. *Fix:* add `is_archived` (and `archived_at`/`archived_by` for symmetry) to `readonly_fields` on both admins.

**Deliberate no-action notes** (documented rulings / spec-pinned, recorded so they are not read as gaps)

1. `pfd_list` is deliberately **not** paginated — commented in the view and the template (`projectfolders/list.html:77-82`): paging a depth-first decorated tree would cut a parent from its children. Not one of the smoke's "five paginated registers".
2. `pdv_restore` re-uses the source revision's `file` object (same stored path, no copy) — consistent with "history is never rewritten, never deleted"; only the missing checksum (L1-I1) is a defect.
3. `pdm_checkin` is open to any member and the lock is explicitly cooperative in-app — a documented ruling, not a missing gate.
4. **No 7.10 verb carries a `tenant_admin_required`/`is_tenant_admin` gate.** The plan pins no such gate for any of the 14 verbs (delete, legal hold, archive, publish), so this is spec-conformant; whether a legal hold should be member-writable is an authorization-policy question I am routing to **security-reviewer**, not filing here.
5. `DocumentTemplateForm`'s no-op `_reject_foreign(self, cleaned, [])` (`Templates.py:44`) is intentional — the register has no tenant-scoped FK — and is commented as such.
6. `ProjectDocument.title` is `blank=False` while `clean()` allows a blank title for `status == "expected"` — the unreachable branch the header asked the lanes to decide. My ruling: leave the model alone and keep the placeholder reachable through the form (which is what the seeded `expected` row and `list.html:98` do); the dead branch is documentation, not a bug. Recorded rather than filed.
7. `core.Document` is not imported, FK'd or migrated — the pinned boundary; `share_register_url` is a read-only lens, correctly.
8. `usage_count`/`is_featured` are a click counter and a shelf; `is_format_locked` is an intent — no page claims otherwise (checked every template's copy for an enforcement claim; none found).
9. Retention deletes nothing: `doc_retention` and `doc_retention_run` only read and raise `ProjectNotification` rows; no page claims a schedule.

**Routing.** performance-reviewer: `doc_repository`'s per-doc-type loop issues one COUNT per choice (`RepositoryOverview.py:39-42`) and `_due_rows` loads every live document per board render — both are their call, not mine. frontend-reviewer: the L1-M2 label and the actions-column status conditions (edit/delete offered on archived/held rows, refused server-side with a message). qa-smoke-tester: no revision in the DB has ever come through `pdv_upload`, so the upload→approve→search-copy chain is asserted nowhere (L1-C1). test-writer: `test_docmgt_views.py` should assert `extracted_text` is populated after a real upload POST and that `pdv_restore` copies the checksum.

### Orchestrator verification of lane 1's Criticals (before filing)

House rule: a load-bearing Critical is verified independently before it is filed, because a lane's
reproduction can be right about the mechanism and wrong about the blast radius. Both of lane 1's
Criticals were re-measured **through the real request path** (`temp/verify_l1_criticals.py`,
`temp/verify_l1_c2_strictmode.py`), not by repeating the lane's isolated probe.

**L1-C1 — CONFIRMED, and worse than filed.** A real `POST` to `pdv_upload` (302, revisions 23 → 24)
created `v3` of a seeded document with `extracted_text=''` and
`extraction_note='The stored file could not be reached on disk.'` — the lane's mechanism is exactly
right. The compounding half is the more serious part and the lane understated it: approving that
upload took the parent's search copy from **103 characters to 0**. So the defect is not merely "search
does not index uploads" — **approving a UI upload silently destroys text an earlier approval or a
re-index had stored on the parent.** The probe revision was deleted and the parent's pointer and
search copy restored; verified byte-for-byte afterwards.

**L1-C2 — CONFIRMED as a defect; the lane's repo-wide scope claim is REFUTED.**
- Measured on this checkout (non-strict): the row is written and the value is silently truncated —
  `action='retention_'`, exactly 10 chars. Note this means the lane's own stated detector
  (`len(action) > 10`) could never fire; the corruption is only visible by reading the value.
- Measured with `sql_mode='STRICT_TRANS_TABLES'` set **for one session only** (never globally, row
  rolled back): **`DataError: (1406, "Data too long for column 'action' at row 1")`**. The lane's
  prediction of a 500 under a strict-mode server is therefore **measured, not theorised** — and
  `STRICT_TRANS_TABLES` is in the default `sql_mode` for MySQL 5.7+ and MariaDB 10.2+, so the
  retention Run would 500 on a normally-configured server.
- **But "a repo-wide grep for other over-length actions returns nothing" is false.** Extracting every
  third-argument literal passed to `write_audit_log`/`log_action` across `apps/` returns **25
  distinct actions longer than 10 characters** — `document_reminders_run` (22),
  `knowledge_resource_publish` (26), `knowledge_resource_archive` (26), `policy_superseded` (17),
  `revision_approve` (16), `document_checkout` (17), `document_archive` (16), `tier_approve`,
  `generate_lot`, `line_delete`, … The overwhelming majority are **procurement 6.19's**, which 7.10
  mirrors — so this is a **pre-existing repo-wide idiom, not a 7.10-original defect.**

**Disposition.** Filed as **Critical** (a measured 500 on a mainline button under the default
production `sql_mode`) but with the scope corrected: **fix 7.10's one instance here, and carry the
repo-wide sweep as a separate item** rather than letting a 7.10-only fix read as the repo being
clean. The shape is identical in 6.19, so the sweep is a cross-module change that does not belong in
a 7.10 close-out.

**Corrected severity/scope for the consolidated block:** L1-C2 keeps Critical; the "only instance"
sentence is struck; the finding text should say *"the 7.10 instance of a repo-wide idiom — 25 other
sites exist, mostly procurement 6.19's; fix 7.10's here and record the sweep."*

### Lane 2 — explorer (serial pass 2)

**Scope check.** Read: all 5 model modules, 5 form modules, 7 view modules, 8 url modules + the 7.10 wiring in `apps/projects/urls/__init__.py`, the 7.10 admin block, `_docmgt` + `--flush` + `_seed_tenant` dispatch, `LIVE_LINKS["7.10"]` + the `parse_catalog()` round-trip, migration `0014`, all 22 templates, `apps/core/crud.py`, `apps/projects/{forms,views}/_common.py`, `views/_helpers.py`, `templates/partials/pagination.html`, and the plan (todo.md:7987-8324) bullet by bullet. Probed (read-only): `manage.py check` → 0 issues; `makemigrations --check --dry-run` → "No changes detected"; `parse_catalog()` → 7.10's five bullet strings match `LIVE_LINKS` keys exactly; `reverse()` on all 7.10 names; a reverse-FK sweep for every model pointing into the 5 new tables; `full_clean()` on an unsaved duplicate root folder; the test client (GET only) over `pdm_list` ×13 lens values and `kne_search` ×5; read-only DB queries for counts/statuses/approvers. Could NOT verify: any runtime mutation, and `--flush` + re-seed identical counts (destructive) — see **L2-I3**.

**Sanity-checks of F-1..F-4**

- **F-1 — PASS.** `_search()` then the whole 7-tuple spec to `crud_list` with `search_fields=[]` (`views/…/Documents.py:54,60-75`). Measured: `?status=nope`→15 rows (junk enum ignored), `?folder=0`→15, `?folder=abc`→15, `?document_type=nope`→15, `?status=draft`→narrows, `?archived=True`→2, `?page=99`→clamps, `?page=abc`→page 1. No 500 on any of the 13.
- **F-2 — PASS.** `from django.db.models import F, Q` (`views/…/Knowledge.py:12`), used `:53-56`. `?q=charter`→200, `?q=a`→200.
- **F-3 — PASS.** `self.fields["project"].disabled = True` inside the instance branch (`forms/…/Documents.py:56-63`), narrowed querysets at `:50-54` from `self.instance.project_id`.
- **F-4 — PASS.** Imported at `urls/__init__.py:57` **and** concatenated `:145`; `/projects/`→200. All seven `_dk_*` modules concatenated (`:156-162`).

**Contract walk** (todo.md line → verdict; only the non-MET rows are shown, all others MET)

- `8137` M1 `clean()` + `unique_together` — **PARTIAL**. Same-project, self-parent and cycle enforced (`ProjectFolders.py:120-129`); constraint exists (`:57-62`). The root-duplicate half does not run on create → **L2-I2**.
- `8143` M1 form narrowed parent — **PARTIAL** (lane 1's L1-M5, not re-filed).
- `8173` M2 `clean()` — **PARTIAL**. Title rule `:302-303` ✓, held+archived `:305-307` ✓, `_id`-first backstop `:314-318` ✓. The two check-out refusals live in the view (`pdm_checkout:179`) and the form (`forms/…/Revisions.py:51-56`), not `clean()` → see **L2-M5**.
- `8181` M3 file rules "in `clean()`" — **DELIBERATELY-MOVED**. Rules exist once (`validate_upload`, `models/…/Documents.py:92-107`), applied by the form's `clean_file` (`forms/…/Revisions.py:36-43`). Defensible (the error attaches to the field).
- `8187` M3 immutability — **MET in substance**. No edit url/view/template; only form is the upload form with `fields=["document","file","change_note"]`. (The plan's literal "everything but `change_note` is `editable=False`" is false — `document`/`file`/`revision_no`/`is_approved` must be editable for the create path — but nothing surfaces them.)
- `8195` M3 `pdv_reindex` — **MISSING under that name**; the behaviour is complete as `pdm_reindex` on the document (`views/…/Documents.py:295-318`), which is what the Model-2 bullet pins.
- `8211` M4 "file required on create" — **MISSING** (lane 1's L1-M4, not re-filed).
- `8224` M5 `kne_publish` Toggle draft/published/**retired** — **DELIBERATELY-CHANGED**. Toggles draft↔published and **refuses** a retired row (`views/…/Knowledge.py:160-163`); retiring is an edit. Documented in the view docstring, not in the plan.
- `8232` `doc_repository` tiles **+ the register with six lenses** — **DELIBERATELY-SPLIT**. All six tile figures present plus four more (`RepositoryOverview.py:23-35`), but the page hosts no register: the register is `pdm_list` at `documents/` with 7 lenses. The plan's `?type=` is `?document_type=`.
- `8235` `doc_retention` — **PARTIAL**. Figures all computed (`RetentionBoard.py:60-67`), Run raises in-app rows only, deduped in the lock (`:92-111`). Held and archived are figures only, with no row list and no click-through → **L2-M6**; the Run's idempotency is weaker than the page claims → **L2-M1**.
- `8238` `kne_search` 4+-character rule — **DELIBERATELY-CHANGED**. Deliberately not applied (documented in the view docstring and the page copy), `category` added to the searched set, shelf from `Meta.ordering`, empty state names the fields (`search.html:74-76`).
- `8249` views layer — **PARTIAL**. Everything holds except "verb in `changes`, never in `action`", which `RetentionBoard.py:112` breaks (lane 1's L1-C2, not re-filed).
- `8262` navigation block — **PARTIAL**. Five keys character-for-character ✓, extra leaf present ✓ (label "Folder Tree" where the plan wrote "Folders" — deliberately the page's own title). The plan asked for a comment explaining **both** `kne_search` **and** `doc_repository` as lenses; only `kne_search` is explained.
- `8283` `--flush` then re-seed identical counts — **PARTIAL/unverifiable here**; the ordering is PROTECT-safe (`:285-296`: knowledge → templates → revisions → documents → folders) and page 2 exists.
- `8285` smoke sweep — **MET as reported** (167/0). **Caveat: the smoke mutates the dev DB (L2-I3).**
- `8298` `test-contract` + `docmgt_*` conftest + 4 test lanes — **MISSING**.
- `8302` todo.md close-out note — **MISSING** (no `### Projects 7.10 — … (close-out …)` section).
- `8308-8319` deferred items — **MET**: none built; each named as another sub-module's on the relevant page.

**Disagreements with lane 1.** None substantive. Two calibrations: (a) L1-I4 is arguably a Minor on its own, raised only as a compounding factor of L1-C1; (b) L1-M3 is right about the mechanism but understates the blast radius — the false claim is in **three** places, not one (see **L2-M5**).

**Findings**

**L2-I1 — Important — `apps/projects/views/ProjectInitiation/Overview.py:14-39,148-152` + `templates/projects/overview.html:8,54-275`**
7.10 is invisible on the Projects **module landing page**. The model-import list has none of the five 7.10 models, the context dict has no 7.10 count, the intro paragraph stops at "…the 7.9 collaboration layer…", and the "Start here" quick-links table ends with 7.9's `Shared Documents`/`My Inbox`/`Activity Feed`. A grep for any 7.10 route name in the template returns **0**.
*Why it matters:* every prior sub-module added its stat cards + quick links + intro mention (7.9 did exactly this in `578eda82`), and 7.10's own landing page breadcrumbs back to `/projects/` — so a user who clicks "Projects" from the document repository arrives at a page that does not acknowledge the sub-module. Live in `LIVE_LINKS` but undiscoverable from the module's front door.
*Fix:* mirror the 7.9 block — add `document_count`/`folder_count`/`retention_due_count`/`knowledge_count` to the view context, and a five-row quick-link group plus the intro clause.

**L2-I2 — Important — `apps/projects/models/DocumentKnowledgeManagement/ProjectFolders.py:130-137`**
The root-folder duplicate-name guard is gated on `self.pk`, so it only runs on **edit**. On create it never fires, and neither Django nor MySQL can cover the gap: `_perform_unique_checks` skips a `unique_together` whose value is `None`, and MySQL treats NULLs in a unique index as distinct. The invariant is asserted in three places that are therefore false — the `Meta` comment (`:59-60`), the `clean()` comment (`:131-132`), and `SKILL.md:865-867`.
*Why it matters:* a user can create two root folders of the same name in one project through the only create path (`pfd_create` → `ProjectFolderForm` → `full_clean()`), and both render identical `full_path`s in the tree and in every folder dropdown.
*Fix:* drop `and self.pk` from the `elif` (or hoist the clash check so it runs on create and edit), and add the two assertions to the `docmgt_*` model lane.

**L2-I3 — Important (review integrity, not a 7.10 code defect) — `temp/smoke_710.py`; header block `.claude/tasks/review-projects-7.10.md:96-100`**
The dev database is **no longer in its seeded state**. Measured on `admin_acme`'s 7.10 rows: **0** revisions pending approval (documented shape: 4); 6 `ProjectNotification` rows of `kind="due_date"` (the seeder creates none — only the retention Run does); **13** `AuditLog` rows whose `action` is the truncated `retention_`, i.e. 13 presses of the retention Run; and documents PDM-00011/12/22 carry `status="approved"` with a moved pointer.
*Why it matters:* the header tells all six lanes to treat the seeded shape as fact; a lane that asserts it from the DB will report a defect that is really a probe artefact. `--flush` + re-seed identical counts can no longer be re-verified without the destructive flush.
*Fix:* record that the seeded-shape block describes the **code**, not the current DB; either have the smoke run inside a rolled-back transaction or restore the touched rows; note that clean re-verification needs `seed_projects --flush`.

**L2-M1 — Minor — `apps/projects/views/DocumentKnowledgeManagement/RetentionBoard.py:97-99` + `retention.html:11,84`**
The dedupe key includes `is_read=False`, so the Run is idempotent only while the reminders are unread: Run → mark read → Run raises the full set again. The docstring ("cannot raise twice") and the page copy ("Pressing it twice changes nothing") state it absolutely.
*Fix:* scope the copy to "while the reminder is still unread", or dedupe on the title alone.

**L2-M2 — Minor — `models/…/ProjectFolders.py:80-82`; `models/…/Revisions.py:108-111`**
Two computed helpers have no reader anywhere: `ProjectFolder.status_css` (the templates read `row.obj.is_archived` directly) and `ProjectDocumentRevision.is_editable` (a constant `False`; no template asks). Same class as L1-M1 — listed so the burn-down closes the set.

**L2-M3 — Minor — `apps/projects/management/commands/seed_projects.py:2320`**
The `_docmgt` docstring says "**25 revisions** … and four left pending approval". The block mints **23** per tenant (DB agrees: 23/tenant). The header's own seeded-shape line says 23. Also at `:61` (the module docstring). *Fix:* change both to 23.

**L2-M4 — Minor — `models/…/Templates.py:54`; `views/…/Templates.py:27`; `documenttemplate/list.html:22-36`**
`DocumentTemplate.document_type` is a bare `CharField(max_length=20, blank=True)` with **no `choices`**, so the plan's "the SAME vocabulary as `ProjectDocument`" is unenforced: a hand-typed "Report" never matches the register's `report`. Separately, `dtm_list` declares a `("document_type", "document_type", False)` filter that **no control sends** — the list template renders only `category` and `is_active` — so it is a lens reachable only by typing the URL (the mirror image of F-1).
*Fix:* give the field `choices=ProjectDocument.DOC_TYPE_CHOICES`, and either render a `document_type` select fed from `extra_context["doc_type_choices"]` or drop the filter.

**L2-M5 — Minor (amplifies lane 1's L1-M3) — `.claude/skills/projects/SKILL.md:941-942`; `.claude/tasks/todo.md:8173-8175`; `models/…/Revisions.py:19-21`**
The claim that a checked-out parent refuses an upload *in the model layer* is stated in three places. Verified: there is no such check in `ProjectDocument.clean()` (`Documents.py:292-324`) or `ProjectDocumentRevision.clean()` (`Revisions.py:115-135`).
*Fix:* correct all three, or move the check into `ProjectDocumentRevision.clean()` as the plan's Model-2 bullet specifies.

**L2-M6 — Minor — `templates/projects/documentknowledge/retention.html:18-25`**
The board's plan parenthetical names "overdue retention, review due, **held rows, archived rows**". Only the due rows are listed (`_due_rows` filters `is_archived=False` by design); held and archived are figures with no table, no lens link and no click-through.
*Fix:* add two held/archived panels, or make the two tiles link to `pdm_list?archived=True` and a held lens.

**L2-M7 — Minor — `models/…/Documents.py:153`**
`ProjectDocument.folder`'s comment cites "the 6.19 container rule". Procurement 6.19 has **no** container/folder concept (the only "container" hits are `container_ref` on an ASN and an unrelated SourcingEvent mention; 6.19's `ProcurementDocument` has no `folder` FK and no PROTECT edge). The rule is Deltek PIM's, correctly attributed in `ProjectFolders.py:20-22` — the 6.19 attribution is spurious. The *behaviour* is real and correct.
*Fix:* strike "(the 6.19 container rule)". (The rest of the 6.19 mirror claim holds; the only 6.19 *defect* carried across is the over-length audit action of L1-C2.)

**Deliberate no-action notes**

1. `pfd_list` is unpaginated on purpose — commented in the view and `projectfolder/list.html:77-81`.
2. `pdv_restore` re-uses the source revision's file object — only the missing checksum (L1-I1) is a defect.
3. `pdm_checkin` is open to any member; the lock is explicitly cooperative in-app.
4. No 7.10 verb carries a `tenant_admin_required` gate; the plan pins none. Whether a legal hold should be member-writable is lane 6's question.
5. `DocumentTemplateForm`'s no-op `_reject_foreign(self, cleaned, [])` is intentional and commented.
6. `ProjectDocument.title` `blank=False` vs the unreachable `clean()` branch: `SKILL.md:900-905` already records it as a close-out decision, so lane 1's "recorded rather than filed" is correct.
7. `core.Document` untouched; `share_register_url` is a read-only lens to a route that exists and honours `?project=`.
8. `usage_count`/`is_featured`/`is_format_locked` — every one of the 22 templates was read for an enforcement claim; none found.
9. Retention deletes nothing; `retention.html:102` states it.
10. `pdv_compare` is metadata-only and says so (`compare.html:8,76-85`); the cross-document and same-revision refusals are messages, not silent renders.
11. The navigation leaf label is "Folder Tree" where the plan wrote "Folders"; the character-for-character rule applies to the five NavERP.md bullet names, which match exactly.
12. `_docmgt` mints `ContentFile` only inside the guard's `else`; the `backdate()` constraint is real and correctly handled.

### Orchestrator verification of lane 2's findings (before filing)

Re-measured independently, through probes rather than by re-reading the lane's citations:

- **L2-I1 — CONFIRMED.** `grep -cE "pdm_list|pfd_list|dtm_list|kne_list|doc_retention|doc_repository" templates/projects/overview.html` → **0**, while 7.9's five routes (`chn_list`, `dsh_list`, `mtg_list`, `ntf_list`, `activity_feed`) are all present. So the omission is 7.10-specific and not a house convention.
- **L2-I2 — CONFIRMED exactly as described.** A **new** `ProjectFolder(tenant=acme, project=<active>, parent=None, name="01 Governance")` passes `full_clean(exclude=["number"])` with **no error**; renaming a *second* existing root to the same name is **refused** (`{'name': ['This project already has a root folder with that name.']}`). The `and self.pk` gate is the cause, and the invariant is indeed claimed in the model comments and in `SKILL.md`.
- **L2-M7 — CONFIRMED.** Procurement's only "container" hits are `container_ref` on `AdvancedShipmentNotice` and an unrelated `SourcingEvent` mention; 6.19 has no folder/container concept. The attribution is spurious.
- **L2-M3 — CONFIRMED.** `25 revisions` appears at `seed_projects.py:61` (module docstring) **and** `:2320` (`_docmgt` docstring); the minted count is 23/tenant and the DB agrees.
- **L2-I3 — CONFIRMED, and it is this session's own residue.** Measured: **0** pending revisions (shape says 4), **6** `kind="due_date"` notifications (the seeder creates none), **13** `AuditLog` rows with `action='retention_'`. Cause: `temp/smoke_710.py` presses real verbs (approve, checkout/checkin, `kne_use`, the retention Run) against the dev DB, and the two verification probes pressed more. **Action taken: the close-out ends with `seed_projects --flush` + `seed_projects` to restore the canonical seeded state, and the header's seeded-shape block is hereby marked as describing the CODE, not the live DB.** (The 13 truncated `retention_` rows are themselves the L1-C2 evidence.)

### Lane 3 — frontend-reviewer (serial pass 3)

**Scope check.** Read in full: all 22 templates under `templates/projects/documentknowledge/**` (line by line, not diffed — they are new in this session), the seven 7.10 view modules, all five form modules, `apps/core/crud.py`, `apps/core/forms/_common.py` (`TenantModelForm`), `apps/projects/forms/_common.py`, `templates/partials/pagination.html`, `static/css/theme.css` (all 428 lines), the five 7.10 model modules, and `.claude/CLAUDE.md` §Filter Implementation Rules / §CRUD Completeness Rules / §Template Folder Structure. **Read-only; no file written, no POST issued.** Probes (all GET): a programmatic set-difference of every `class="…"` token in the 22 files against the class set extracted from `theme.css`; a second pass comparing every *rendered* `class="badge X"` against `theme.css` over 26 routes; per-file tag-balance and `{% if %}`/`{% for %}`/`{% block %}`/`{% comment %}` counts; per-table `colspan` vs `<th>` count; a `{#` leak scan; a label-`for`↔`id` and icon-control accessible-name sweep; a scan of every `{{ }}`/`{% %}` inside a single-quoted JS string in an `on*` handler; `ProjectDocumentForm(title="", status="expected").is_valid()`; live DB status counts; and one rendered HTML dump per page through the test client as `admin_acme`. Cannot verify browser JS execution — the one claim that depends on it (**L3-I2**) is split below into what was measured and what is spec, and the repo documents the identical mechanism as **L42**.

**Sanity-checks of F-1..F-4** (re-verified from the rendered HTML, not by re-reading the fix)

- **F-1 — PASS.** Tenant 1 has 22 documents / 0 drafts. Rendered: no lens → "Showing 1–15 of 22"; `?status=approved` → 17; `?status=draft` → empty state (correct, 0 drafts); `?status=nope` → 22 (junk ignored, L11); `?archived=True` → 2 rows. All eight selects in `pdm_list`'s filter bar now narrow.
- **F-2 — PASS.** `GET /projects/knowledge/search/?q=charter` → **200** with a rendered result table; no `NameError`.
- **F-3 — PASS.** `pdm_edit` renders `<select name="project" class="form-select" required disabled id="id_project">` — present, disabled, value from the instance.
- **F-4 — PASS.** `doc_repository` renders 200 with the `href="/projects/"` breadcrumb; every 7.10 breadcrumb's first link is live.

**Coverage — clean categories (no findings filed)**

- **Design-system conformance / L33 — CLEAN, verified twice.** Every static class token in the 22 files either exists in `theme.css` or is a Tailwind utility the Play CDN generates (67 distinct classes). Rendering all 26 routes yields badge classes `{badge-green, badge-info, badge-amber, badge-red, badge-muted, badge-slate}` — **no** `-success`/`-danger`/`-warning`, no `stat-icon` misuse, no invented name. All four `status_css` properties resolve to real colour names. Layout classes `detail-grid`, `form-grid`, `form-actions`, `filter-bar`, `table-wrap`, `table-actions`, `empty-state`, `.req`, `pagination`, `badge-group`, `form-select` all exist. `TenantModelForm` stamps `form-input`/`form-select`/`form-textarea`/`form-check` on every widget, so the `{{ field }}` loops are styled without per-template work.
- **Comment leaks / markup validity — CLEAN.** Zero `{#` in the 22 files. Every tag balances; every `{% if %}`/`{% for %}`/`{% block %}`/`{% comment %}` balances; **every** `colspan` equals its table's `<th>` count (all 12 tables). No rendered page leaves a `{%`/`{{` behind.
- **CSRF / POST hygiene — CLEAN.** 40 `<form method="post">` blocks, all 40 carry `{% csrf_token %}`; no form is missing a `method`.
- **Accessibility — CLEAN.** Across the 5 form pages, 4 list pages, `pdm_detail`, `pdv_upload`, `kne_search` and `doc_retention`: **0** controls with neither a matching `<label for>` nor an `aria-label`, and **0** orphan `for=` targets. Every icon-only control carries `title`. Colour is never the only status carrier.
- **Pagination guards (L9) — CLEAN.** `partials/pagination.html` guards both `previous_page_number` and `next_page_number` and preserves every GET param except `page`. Every paginated register includes it. (The one page whose *window* is empty is lane 1's L1-I3.)
- **Badges — CLEAN.** All read the model's exact CHOICES via `status_css` + `get_status_display`; the Boolean badges correctly branch (no `get_*_display` exists for them).
- **Filter-bar contract — CLEAN.** All six filter forms send `name="q"` plus real `<select>`s; pk comparisons use `|stringformat:"d"`, never `|slugify`; every select re-selects from `request.GET`; `{{ q }}` is populated because `crud_list` always sets it even when `search_fields=[]`.
- **Empty-state / structure — CLEAN.** All five registers use the same pattern; all five have a filter form, an Actions column, a csrf+confirm delete, and an `.empty-state`; all four detail pages end in a `.form-actions` row with a Back link **and** a POST-Delete; no list page has a "Back" (consistent — they carry cross-links instead). Paths conform to CLAUDE.md §Template Folder Structure.
- **Copy honesty on the six pinned rulings — CLEAN** except L3-I3. `is_format_locked` is called an *intent* on both pages that mention it and the badge reads "Format lock recorded"; the check-out lock is called cooperative in-app on three pages; "Nothing here deletes anything on a schedule" appears on four; `usage_count` is called a click counter on four; `is_featured` is called a shelf on three; the share register is a read-only lens and `dtm_detail:60` says generating from a standard is **not** offered.
- **The four new `delete.html` pages — the refusals are real.** `pfd_delete:12` matches `ProjectFolders.py:140-147`; `pdm_delete:16-17` matches `Documents.py:148-157`; `dtm_delete`/`kne_delete` state **no** refusal and correctly so — neither view has one.

**Disagreements with lanes 1–2**

- **Lane 1's routing note is half wrong.** It routed "edit/delete offered on archived/held rows, **refused server-side** with a message". Delete is refused (`Documents.py:148-157`); **edit is not refused anywhere** — `pdm_edit` (`:124-138`) and `ProjectDocumentForm` have no archived/hold guard. So the list offering Edit on an archived row is a *working* action, and it is the detail page that hides it. Filed as **L3-M2** with that correction.
- **Lane 1's no-action note 6 rests on a false premise** (disposition still fine, fact isn't). It says the blank-title placeholder is "reachable through the form". Measured: `ProjectDocumentForm().fields["title"].required is True`; a blank title with `status="expected"` is rejected with `['This field is required.']`; the seeded `expected` rows carry the title `"Decommissioning plan (slot)"`; `ProjectDocument.objects.filter(title="").count() == 0`. The form cannot produce a blank-title row, and the seven `|default:"expected placeholder"` branches are unreachable. Folded into **L3-I3**.
- Lane 2's L2-M2 is confirmed — the folder templates read `is_archived` directly, and `ProjectFolder.status_css` is the only unread `status_css`.

**Findings**

**L3-I1 — Important — `knowledgeentry/list.html:90-92` and `knowledgeentry/detail.html:14-16`** (view: `Knowledge.py:160-163`)
`kne_publish` **refuses a `retired` row** and redirects with an error ("edit it back to draft before publishing it again"), but both templates render the button unconditionally. On a retired row `k.status == 'published'` is False, so the control renders as a **Publish** button whose confirm says *"Publish KNE-00004?"* — a promise the server will not keep.
*Measured:* tenant 1 has 2 retired entries; `GET /projects/knowledge/38/` renders `action="/projects/knowledge/38/publish/" onsubmit="return confirm('Publish KNE-00004?');"` immediately below a `badge-muted` **Retired** badge, and `?status=retired` renders the same form as an icon button `title="Publish"`. `POST` → 302 and the status stays `retired`.
*Why it matters:* a dead primary-looking action on the sub-module's main library page, in the state where a user is most likely to press it. The flash-message advice is unreachable from the button that triggers it.
*Fix:* wrap both forms in `{% if k.status != 'retired' %}` and render the hint the view already gives in the `{% else %}`.

**L3-I2 — Important — `projectfolder/list.html:62,65` and `projectfolder/detail.html:13,98`**
Four `onsubmit="return confirm('…')"` handlers interpolate a **user-authored** string — the folder name — inside a single-quoted JS literal without `|escapejs`.
*Measured:* the template engine escapes `'` to `&#x27;` — rendered `confirm('Delete folder Bob&#x27;s Docs? x');`. HTML attribute values are character-reference-decoded before an inline handler is compiled, so the handler body the browser parses is `…confirm('Delete folder Bob's Docs? x');` — a **SyntaxError**. A throwing `onsubmit` does not `preventDefault`, so the form submits **unconfirmed**. With `|escapejs` the render is `Bob\u0027s Docs`, which survives attribute decoding.
*Why it matters:* a documented house lesson with a documented fix, not a novel risk — `templates/procurement/spendanalytics/spendrule/list.html:35,169` states the mechanism verbatim and applies the fix, and `hrm/candidates/candidate/list.html:80` does the same. **7.10 is the third recurrence of L42's shape.** The blast radius is bounded (`pfd_delete` still refuses a non-empty folder; the archive toggle is reversible), which is why this is Important and not Critical — but "Delete folder" is a confirmation whose whole job is to appear, and it silently won't.
*Fix:* `{{ row.obj.name|escapejs }}` / `{{ obj.name|escapejs }}` at all four sites.

**L3-I3 — Important — `projectdocument/form.html:33`** (model: `Documents.py:157`)
The page instructs: *"Set **Status** to *Expected* to create a named placeholder before the file exists — that is the one state where a title may be left blank."* That is false in the same page's own render: `title` is `blank=False`, so the loop at `:17` prints `<span class="req">*</span>` beside **Title** and the field is required in every status.
*Measured:* `ProjectDocumentForm().fields["title"].required is True`; a blank title with `status="expected"` → `is_valid() == False`, `errors == {'title': ['This field is required.'], …}`; `filter(title="").count() == 0`; the seeded `expected` row carries a real title.
*Why it matters:* an instruction the form forbids, on the create page, contradicting a required-marker two lines below it. It is also the rendered half of the model inconsistency the header asked the lanes to decide: because the state is unreachable, the seven `|default:"expected placeholder"` branches are dead markup, and `retention:41` presents the fallback as a real document state.
*Fix:* replace the sentence with the truth — "An *Expected* placeholder still needs a title: it is the name the file will arrive under." — and drop the dead `|default:` branches (or flip `title` to `blank=True` and make `clean()`'s existing branch live). Lane 1's disposition — leave the model, fix the copy — is the cheaper of the two.

**L3-M1 — Minor — `projectdocumentrevision/form.html` (whole file)**
`pdv_upload`'s GET page is **orphaned**: `grep -rn "pdv_upload" templates/` returns exactly one hit — the POST `action=` on `pdm_detail:233`. No page renders a link to it, so the standalone upload form (breadcrumb, lock warning card, help text, Cancel) is reachable only by typing the URL, and `pdm_detail` re-renders its own inline copy of the same two fields on validation failure.
*Fix:* link it (an "Upload a revision" button in `pdv_list`'s `page-actions`) or delete the template and keep the inline form as the only path.

**L3-M2 — Minor — `projectdocument/list.html:116` vs `projectdocument/detail.html:11`**
The list always renders the pencil; the detail page wraps Edit in `{% if obj.status != 'archived' %}`. `pdm_archive` sets `status="archived"` and restores it on un-archive, and **nothing refuses an edit of an archived document** — `pdm_edit` and `ProjectDocumentForm` have no status guard. So the detail page hides a working action, and the two sibling pages disagree.
*Fix:* drop the `{% if %}` on `detail.html:11`, or gate both the pencil and the view on the same condition.

**L3-M3 — Minor — `projectdocument/delete.html:25`**
The button labelled **"Archive it instead"** links to `{% url 'projects:doc_retention' %}` — the retention board, whose only per-row control is an eye icon and which carries no archive action at all. The document's actual archive form is on the page the **Cancel** button already points at.
*Fix:* point it at `{% url 'projects:pdm_detail' obj.pk %}` (ideally `#archive`), or fold it into Cancel and drop the third button.

**L3-M4 — Minor — `documenttemplate/delete.html:12`** (same wording in `views/…/Templates.py:102` and `models/…/Templates.py:61`)
*"a retired standard stays readable and leaves the **"start from this" list**"* names a list that does not exist anywhere in the UI. `dtm_detail:60` states the opposite ruling plainly, and `grep -rn "start from this" templates/` returns only this one line.
*Fix:* reword to "leaves the active list on the Standards register".

**L3-M5 — Minor — `knowledgeentry/search.html:74`**
The empty state interpolates the **raw** filter value: *"…or category, within the {{ kind_filter }} kind"* renders "within the lesson_learned kind". Every other surface shows the choice label.
*Fix:* pass the display label from the view, or look it up from `kind_choices`.

**Deliberate no-action notes**

1. `pfd_list`'s unpaginated tree and the `.pagination` div used as a plain count footer — the comment explains it; `.pagination` exists and renders correctly.
2. `pdm_list`'s archive lens labelled "Live register" is lane 1's L1-M2. One added data point: `retention.html:23`'s "In the live register" tile genuinely means `is_archived=False`, so the two pages use the same phrase for different sets — relabel the register to "Any state" and the tile can stay.
3. `retention.html`'s held/archived rows and the idempotency claim are lane 2's L2-M6/L2-M1; reproduced, not re-filed.
4. `pdv_compare`'s `same_checksum → "Different bytes"` on a restored revision is lane 1's L1-I1; the template is otherwise correct.
5. `pdm_detail:66`'s `obj.extraction_note` is lane 1's L1-I4 — confirmed dead, not re-filed.
6. `dtm_list`'s unsent `document_type` filter is lane 2's L2-M4; not duplicated.
7. Detail-header action sets differ across siblings, but every one still ends in the same `.form-actions` Back + Delete row; noted for consistency, not filed.
8. `doc_repository` links only to `pdm_create` and to recent documents' detail pages — no link to the register, folder tree, retention board, standards or knowledge. The sidebar carries all five bullets, so a user is not stranded. Not filed.
9. `pdm_archive`'s un-archive guesses the status (`"approved" if current_revision_no else "draft"`) — an `in_review`/`superseded` document comes back wearing a different badge. A state-machine question in the view, so it belongs to code-reviewer; flagged here only so the burn-down does not read it as a UI bug.
10. `share_register_url` is a hardcoded path rather than a `{% url %}`; the rendered link is correct, so it is a maintainability note.

### Orchestrator verification of lane 3's findings (before filing)

- **L3-I2 — CONFIRMED.** `grep -rc escapejs templates/projects/documentknowledge/` → **zero files**; all four `onsubmit` sites interpolate the bare name (`projectfolder/list.html:62,65`, `projectfolder/detail.html:13,98`). Rendered probe: `{{ name }}` → `confirm('Delete folder Bob&#x27;s Docs? x');` vs `{{ name|escapejs }}` → `Bob\u0027s Docs`. The repo's own L42 precedent is real and applies the fix in `procurement/…/spendrule/list.html:169` with the mechanism documented at `:35`. **Third recurrence — and the fix is a four-token change.**
- **L3-I1 — CONFIRMED.** `KNE-00004` ("Discovery retrospective…") is `retired`; its detail page renders `action="/projects/knowledge/38/publish/" onsubmit="return confirm('Publish KNE-00004?');"` under a `badge-muted` Retired badge, and `?status=retired` renders the same form. `POST` → **302 with the status still `retired`**, i.e. the button's promise is refused.
- **L3-I3 — CONFIRMED.** The instruction is on the create page and the field is required in every status; the seeded `expected` row has a title. Lane 3's correction of lane 1's no-action note 6 is accepted — the premise was wrong even though the disposition (leave the model, fix the copy) stands.
- **L3-M2 — ACCEPTED.** Lane 3's correction of lane 1's routing note is right: `pdm_edit` has no archived/hold guard, so Edit on an archived row *works*, and it is the detail page that hides it.

### Lane 4 — performance-reviewer (serial pass 4)

**Scope check.** Read in full: the 7 view modules under `views/DocumentKnowledgeManagement/`, all 22 templates, the 5 model modules, `apps/core/crud.py`, migration `0014`. **Measurement method:** `CaptureQueriesContext` + `connection.queries` through the Django test client as `admin_acme` on the live dev DB — **GET only, no writes, no `--flush`**, so nothing was added to the residue lane 2 recorded. 26 GET routes measured, plus 9 sibling 7.1–7.9 routes for the house bar. Every SQL statement was labelled; every claim below is a captured statement or an `EXPLAIN`, not a reading. Fixed per-request overhead is 7 queries (session, auth user, tenant, branding, BEGIN/UPDATE/COMMIT), measured identically on every route.

**Sanity-checks of F-1..F-4 (performance angle)**

- **F-1 — PASS.** `pdm_list` = **12 queries** with and without `?q=`; the filter spec runs before `paginate` and all 8 lenses narrow with **0 per-row queries** (project/folder/owner/task/milestone all in `select_related`, `Documents.py:53`).
- **F-2 — PASS.** `kne_search?q=charter` = 9 queries / 200, no `NameError` — but the sweep is issued **twice** (L4-I2).
- **F-3 — PASS.** No query impact: `pdm_edit` = 13, `pdm_create` = 12.
- **F-4 — PASS.** All 26 routes `reverse()` and render 200, so the un-concatenated-module shape is not repeated.

**Measured query counts** — 26 GET routes, seeded tenant (22 docs / 12 folders / 23 revs / 16 standards / 17 entries). House bar measured alongside: 7.1–7.9 registers **10–12**; computed boards `projects:overview` **72**, `activity_feed` **18**.

| route | queries | page-specific | verdict |
|---|---|---|---|
| `doc_repository` | **29** | 22 | above registers (12), below 7.1 `overview` (72); **20 COUNTs**, 11 from one loop → L4-I4 |
| `pdm_list` / `?q=charter` | 12 / 12 | 5 | **at the bar**; 0 per-row; payload → L4-I3 |
| `pdm_detail` | 14–17 | 7–10 | at the bar; +1/ancestor level; 1 redundant → L4-M2 |
| `pdm_create` / `pdm_edit` / `pdm_delete` | 12 / 13 / 9 | 5/6/2 | at the bar |
| `pfd_list` | 10 | 3 | **at the bar**; whole tree, 1 grouped count (not 1/folder) |
| `pfd_detail` root / child | 13 / 14 | 6 / 7 | at the bar; +1 per ancestor level → L4-M4 |
| `pfd_create` / `pfd_edit` / `pfd_delete` | 9 / 10 / 11 | 2/3/4 | at the bar |
| `pdv_list` | 11 | 4 | **at the bar**; `rev.is_current` costs 0 (cache) |
| `pdv_compare` empty / populated | 7 / **15** | 0 / **8** | populated is 2× its siblings → L4-M1 |
| `pdv_upload` | 8 | 1 | at the bar |
| `dtm_list` | 9 | 2 | **below the bar** |
| `dtm_detail` / `dtm_create` / `dtm_edit` / `dtm_delete` | 10 / 8 / 9 / 8 | 3/1/2/1 | `dtm_detail` 3 FKs unjoined → L4-M1 |
| `kne_list` | 10 | 3 | at the bar |
| `kne_search` no-match / match | 9 / 10 | 2 / 3 | **2 identical COUNTs** → L4-I2 |
| `kne_detail` / `kne_create` / `kne_edit` / `kne_delete` | 11 / 10 / 11 / 8 | 4/3/4/1 | `kne_detail` 3 FKs unjoined → L4-M1 |
| `doc_retention` | 12 | 5 | at the bar in **count**; payload + unbounded table → L4-I1 |

**Coverage — clean categories (no findings filed)**

- **No N+1 in any of the 5 paginated registers.** `pdm_list` 12, `pdv_list` 11, `kne_list` 10, `dtm_list` 9, `kne_search` 9–10 — all constant against a 15-row page, and every FK the templates touch is in the view's `select_related`.
- **`ProjectDocumentRevision.is_current` is NOT an N+1 — measured 0 queries.** Django's reverse manager populates the parent cache, so `rev.document.current_revision_no` costs nothing.
- **`_decorate()` issues exactly one grouped count, not one per folder.** `pfd_list` = 10 queries with 12 folders → 3 page queries.
- **Bounded row sets where they exist:** `pfd_detail`'s document list capped at 50 with a count footer; `doc_repository`'s recent list capped at 10; all five registers paginate at 15 before slicing. `doc_repository`'s `retention_due` bounds its column set with `.only(...)`.
- **Writes:** `kne_use` is atomic `F()+1` with no read-modify-write; `pdv_approve`/`pdv_delete`/`pdv_upload` take the parent row lock; no per-row `.save()` loop in any view. `file_sha256` streams and rewinds; `extract_text` frees each page's cache.
- **No `objects.all()`, no `list(qs)` on a register, no cross-tenant read, no unbounded slice.**

**Disagreements with lanes 1–3**

- **Lane 1's routing of `doc_repository`:** the 11-COUNT loop is confirmed, but the page is **not** "materially above its siblings" — 29 is *below* 7.1's own `overview` at 72. The grade rests on the §5 rule (one aggregate, not one query per stat card), not on an outlier comparison.
- **Lane 1's `_due_rows` routing:** confirmed (1 SELECT, all columns); the lane implied a query-count problem — it is a **payload/unbounded-render** problem; the count is 1 and constant.
- **Lane 1's L1-C1 has a performance side-effect worth recording:** approving a UI upload overwrites the parent's search copy with `""`, which *shrinks* the TextField payload L4-I1/I3 worry. Not re-filed; no grade changes.

**Findings**

**L4-I1 — Important — `RetentionBoard.py:42-43` + `templates/.../retention.html:38`**
`_due_rows` runs `ProjectDocument.objects.filter(tenant, is_archived=False).select_related("project").order_by("number")` with **no `.only()`/`.defer()`**, so it pulls every column of every live document — including `extracted_text`, a TextField capped at **200 000 chars** — to read two date columns in Python. The board then renders `{% for row in due %}` with **no Paginator**, so the row set is up to 2 rows per live document.
*Growth:* linear in live documents × the 200 000-char cap → **≈4 MB per render at 20 live docs and ≈40 MB at 200 (10×)**, and **400 unpaginated rows** at 10×. At 1× the seeded text is tiny, so this is a bound, not a current cost. `doc_repository`'s equivalent figure already does `.only(...)` — the two boards disagree.
*Fix:* add `.defer("extracted_text")` (or an explicit `.only(...)`) and wrap the due table in `crud.paginate`.

**L4-I2 — Important — `Knowledge.py:68-69,77-80`**
`kne_search` builds `rows = _page(request, qs)` **and** `"total_count": qs.count()`. Measured: `?q=charter` issues **two byte-identical `COUNT(*)` statements carrying the full 5-field `icontains` sweep**, then a third SELECT for the page. `rows.paginator.count` is already that number.
*Growth:* each sweep is a full scan with 5 leading-wildcard `LIKE`s — **unindexable at any size** — so the duplicate is a 2× multiplier on the one unbounded operation on the page.
*Fix:* `"total_count": rows.paginator.count` (one line, halves the sweep).

**L4-I3 — Important — `Documents.py:52-53`, `ProjectFolders.py:84-85`, `Knowledge.py:24-26,49-50`, `RepositoryOverview.py:36-37`**
Four list/detail querysets load a TextField no template on the page reads. Measured: `pdm_list`'s row SELECT **includes `extracted_text`** and `projectdocument/list.html` never references it; `pfd_detail`'s 50-row document list and `doc_repository`'s 10-row recent list likewise; `kne_list`/`kne_search` load `body` for all 15 rows while rendering only `title`/`summary`.
*Growth:* per page render at the cap — `pdm_list` ≤3.0 MB, `pdv_list` ≤3.0 MB, `doc_repository` ≤2.0 MB, **`pfd_detail` ≤10.0 MB (50 rows)**; `kne_list`/`kne_search` are worse because **`body` has no cap at all** (a bare TextField, unlike the capped `extracted_text`). Linear in page size × row size.
*Fix:* `.defer("extracted_text")` on the four document querysets; `.defer("body")` on both knowledge querysets; annotate `Length("extracted_text")` where `pdv_list` needs only the count; and give `body` a `MaxLengthValidator`.

**L4-I4 — Important — `RepositoryOverview.py:38-42`**
The `by_type` loop issues **one `COUNT(*)` per `DOC_TYPE_CHOICES` entry**: measured **11 COUNT statements for 11 choices**. `doc_repository` is 29 queries of which **20 are COUNTs**; this loop is 11 of them.
*Growth:* the query count is **constant in rows** (11 forever) but each is a separate round-trip and index probe, so at 10× the round-trips stay 11 while the scans grow linearly. Exactly the §5 rule ("multiple KPIs over one table should share a single aggregate query").
*Fix:* one grouped aggregate — `documents.values("document_type").annotate(n=Count("id"))` mapped to labels — collapsing 11 round-trips to 1 and the board from 29 to 19.

**L4-M1 — Minor — `Revisions.py:198-214` (`pdv_compare`), `Knowledge.py:84-86` (`kne_detail`), `Templates.py:33-35` (`dtm_detail`)**
No `select_related` on three detail views. Measured: `pdv_compare?a=&b=` = **15 queries, 8 page-specific** — `a` (1), `b` (1), **`a.document` and `b.document` = two SELECTs of the *same* row**, and four user FKs; with `select_related` it is 2. `kne_detail` = 11 (4 page-specific) although `kne_list` already joins all three; `dtm_detail` = 10 (3 page-specific).
*Fix:* `select_related("document","document__project","uploaded_by","approved_by")` on both `pdv_compare` lookups; mirror `kne_list`'s and `dtm_list`'s `select_related` in the two detail views.

**L4-M2 — Minor — `views/Documents.py:93` with `models/.../Documents.py:277-288`**
`pdm_detail` loads `revisions` (1 query) and then calls `obj.current_revision`, which is `self.revisions.filter(is_approved=True, revision_no=...)` — a `.filter()`, so it **bypasses the loaded list**. Measured directly: **1 query** with the rows already in memory, and `prefetch_related("revisions")` does **not** help (still 1).
*Growth:* constant 1 query, but it is the exact class the house lesson records (7.8 `tsk_detail` 31→13). *Fix:* derive it in Python — `next((r for r in revisions if r.is_approved and r.revision_no == obj.current_revision_no), None)` — and pass `revisions` as a list so `detail.html`'s `revisions|length` does not force a second evaluation.

**L4-M3 — Minor — `models/.../ProjectFolders.py:63-67`, `models/.../Documents.py:219-225`, `models/.../Revisions.py:87-89`**
Index audit of the 10 declared in `0014`, against the filters and orderings actually issued:
- **`pfd_tnt_archived_idx` has no reader.** No query filters `ProjectFolder` by `is_archived` (grep = 0 hits; `pfd_list` filters in Python). Pure write overhead on every folder insert/update. *Fix:* drop it, or give the tree a real `?archived=` SQL lens.
- **`ProjectDocument.classification` is unindexed** although `pdm_list` offers `?classification=` as one of its eight lenses — `EXPLAIN` falls back to the `(tenant, number)` unique index + `Using filesort`, while the five sibling filters in the same `Meta.indexes` list each get their own index. *Fix:* add `models.Index(fields=["tenant","classification"], name="pdm_tnt_class_idx")`.
- **`ProjectDocumentRevision.is_approved` is unindexed** although `pdv_list` offers `?is_approved=` and `current_revision` filters on it. *Fix:* `models.Index(fields=["tenant","is_approved"], name="pdv_tnt_approved_idx")`.
- Verified **used**: the other 8 indexes each appear as the chosen key in `EXPLAIN` for their lens.

**L4-M4 — Minor — `models/.../ProjectFolders.py:84-102,142-150`**
`ancestor_chain()` walks `node.parent` in a Python loop — **1 query per ancestor level**. Measured on fresh instances: depth-1 folder `full_path` = **1 query**, root = **0**; `_is_descendant_of` cold = **1 query** for a depth-1 candidate (called from `clean()`, i.e. on every `pfd_edit` POST). `_decorate`'s `walk()` recurses once per level and the model imposes **no depth cap**, so a chain deeper than Python's frame limit raises `RecursionError` on `pfd_list`. The seeded tree is depth **1**, so this is a bound, not a cost.
*Fix:* expose `_decorate`'s pk→parent map so `full_path`/`_is_descendant_of` walk in memory, and add a depth guard.

**L4-M5 — Minor — `Documents.py:38-47`; `models/.../Knowledge.py:111-112`**
Two comments measurement contradicts: `Documents.py` claims the `extracted_text` sweep "runs **at most once** per page render" — measured **2** statements carry it at `?q=charter` (the Paginator's COUNT and the page SELECT) and **0** at `?q=abc`, so the 4-character rule works but the "once" does not; and `Knowledge.py` claims `kne_tnt_feat_idx` "serves the shelf query" — measured, the default register lens picks the `(tenant, number)` unique index and `filesort`s, and the index is chosen only for the filtered `?is_featured=True` facet.

**L4-M6 — Minor (code-derived, deliberately not measured) — `RetentionBoard.py:83-111`**
`doc_retention_run` opens a `transaction.atomic()` **per in-window row** and inside it issues `select_for_update` + `exists()` + `create()` — ≈3 statements and 2 transaction-control round-trips per document. At the seeded 20 live documents that is ~60 statements / 20 transactions per press; at 10× ~600 / 200. The per-row lock is the documented authoritative dedupe, so this is **not** filed as a defect — but the loop could run inside one `atomic()` over a single locked fetch of the in-window ids and keep the same guarantee. Not measured: the route is POST-only and posting would add residue.

**Deliberate no-action notes**

1. **Every 7.10 list `filesort`s** — `EXPLAIN` shows `Using filesort` on all five default lenses because no declared index carries the ordering column. This matches the app-wide reference pattern (no list in the app indexes its ordering column), so it is an app-wide pass, not a 7.10 fork.
2. `pfd_list`'s unpaginated whole-tree render is deliberate and commented; measured 3 page queries at 12 folders.
3. `pdv_list`'s `rev.is_current` per row costs **0 queries** — not filed.
4. `doc_repository`'s `projects(tenant)` context is never rendered by `overview.html`, so it is lazy and costs **0 queries**.
5. `kne_search`'s 1-character rule over `body` is documented; the finding is the duplicate evaluation (L4-I2), not the rule.
6. `pdv_upload` = 8 queries; `file_sha256` streams in chunks and `extract_text` is bounded with per-page cache flushes — no memory finding.
7. The 14 POST-only verbs are outside this lane's GET measurement; they answered 405 in the smoke and add no residue here.

### Orchestrator verification of lane 4's measurements (before filing)

- **Query counts — CONFIRMED exactly.** Re-measured independently with `CaptureQueriesContext`: `doc_repository` **29 queries / 20 COUNTs**, `pdm_list` **12 / 1**, `kne_search?q=charter` **9 / 2**, `kne_search?q=e` **10 / 2**, `pdv_compare` (empty) **7 / 0**, `doc_retention` **12 / 4**. Every number the lane published reproduces, including the two that carry findings (the 11-COUNT `by_type` loop inside `doc_repository`'s 20, and the duplicate COUNT on `kne_search`).
- **L4-M3 index audit — CONFIRMED.** No query anywhere filters `ProjectFolder` by `is_archived` (grep = 0 hits), so `pfd_tnt_archived_idx` has no reader; `classification` appears in no index declaration despite being a `pdm_list` lens; `ProjectDocumentRevision`'s only declared index is `pdv_tnt_document_idx`, so `is_approved` is unindexed despite being a `pdv_list` lens and a `current_revision` filter.
- **L4-I1/I3 growth figures are bounds, not current costs** — the lane says so itself, and at 1× the seeded `extracted_text` is small (measured 1 182 chars across 20 rows). Filed at Important because the fix is one `.defer()` and the cap is 200 000 chars.

### Lane 5 — qa-smoke-tester (serial pass 5)

**Scope check.** Probed by live request only, as `admin_acme` / `admin_globex` and as a throwaway tenant admin, with `Client(raise_request_exception=False)` + `setup_test_environment()`. Covered: the upload→approve→search chain for `.txt` / a real-text-layer `.pdf` / `.png` / `.zip` (including `extract_text` on the *saved* FieldFile as the counterfactual); the whole revision state machine under abuse; `--flush` reasoning + the plain re-seed file-count invariant; the retention Run in the state the page claims; degenerate tenants/documents/folders/knowledge; `?page=` and `?q=` edges on all five registers + `kne_search`; cross-tenant IDOR for the five POST verbs the smoke omits plus `pdv_upload`'s POST body; `MEDIA_URL` serving in a clean process; the folder tree's `?project=` lens, its `?q=` search, and the cycle guard. **Could not** run `--flush` (destructive, other lanes need the data) — read `handle()`/`_docmgt` and reasoned, then verified the file-count invariant on a safe plain re-run. Could not verify browser JS (L42) or re-measure lane 4's counts. **Residue:** every probe ran on a tenant created and then deleted (`l5-710-*`); final DB identical to the pre-probe snapshot — acme 12/22/23/0 pending/16/17, globex 12/22/23/4 pending/16/17, `AuditLog` total unchanged at **6297** with 0 tenant-NULL rows, 0 media delta from the re-seed. **Three orphan files could not be deleted (sandbox denied the `rm`):** `media/projects/documents/2026/09/{gamma.pdf,delta.png,epsilon.zip}` (599/113/21 B, referenced by no row). `l1c1-probe.txt` is **pre-existing, not lane 5's** (the orchestrator's L1-C1 probe). No code/template/file edited, no `git add`/`commit`; probe scripts left in gitignored `temp/l5_*`.

**Sanity-checks of F-1..F-4** — all four **PASS** at runtime.
- **F-1** — `pdm_list`, 17 lens values: narrowing proven where the result is under a page (`?q=PDM-00001`→1, `?q=PDM-0000`→9, `?status=draft`→0, `?document_type=charter`→2, `?archived=True`→2) and `?status=approved`→"Showing 1–15 of 17" of 22; every junk value is ignored without a 500.
- **F-2** — `kne_search` 200 for `?q=charter`, `?q=a`, `?q=`, `?q=zzzznope`, `?q=charter&kind=nope`, `?q=charter&kind=lesson_learned`; filters correctly (`?q=retro`→2, `?q=a`→15, `?q=zzzznope`→0). No `NameError`.
- **F-3** — `GET pdm_edit(PDM-00016)` renders `<select name="project" class="form-select" required disabled id="id_project">`.
- **F-4** — `GET /projects/` → 200 and `GET /projects/activity-feed/` → 200.

**Reproductions / refutations of lanes 1–4's runtime claims**
- **L1-C1 — REPRODUCED, both halves, end to end.** Real `POST pdv_upload` of a `.txt`: `extracted_text=''`, `extraction_note='The stored file could not be reached on disk.'`, while `extract_text(<the same saved FieldFile>)` returns the full text — so the note is false and the caller is the bug. Approving took the parent's copy from `'ALPHATOKEN7788 the quick brown fox…'` (103 chars) to `''`; the register then returned **0 rows** for the old token and 0 for the new one. `pdm_reindex` repaired it both times. Same for a hand-built **real-text-layer `.pdf`** (`extract_text(v3.file)` → `'PDFTOKEN4455 report body'`, stored `''`). `.png`/`.zip` got the **wrong** note (`unreadable path`, not `NOTE_NO_TEXT_LAYER`).
- **L1-I1 — REPRODUCED.** `pdv_restore` → new revision `checksum=''` while the source is `d4580ce0…`; `pdv_compare` prints **"Different bytes"** for a byte-identical restore, and the sentence at `compare.html:82` sits inside the `same_checksum` branch so it can never render.
- **L2-M1 — REPRODUCED.** Run→1, Run→1, mark read, Run→**2**, against a page that says "cannot raise twice".
- **L3 no-action note 9 (un-archive status guess) — REPRODUCED** and filed below as L5-I2.
- **L1-M5 — CONFIRMED** (edit form excludes only self; the child is offered).
- **Lane 1's coverage §"cycle enforced" and lane 2's contract-walk line 8137 — REFUTED.** The cycle guard is dead; see **L5-C1**.
- L2-I3's drift signature confirmed independently (acme 0 pending vs globex 4). Lane 4's counts not re-measured.

**Coverage — clean categories (no findings filed)**
Revision numbering sequential across two uploads (1→2) and gapped after deleting an unapproved revision (→5), as documented. Upload refused while checked out (200 + visible error, 0 rows). Approve twice / at-below-pointer / under hold all refused with the pointer unmoved. Restore-unapproved, delete-approved, delete-current all refused. `pdm_delete` works on a document with no approved revision. Upload validation: no file / `.exe` / no extension all refused with a visible error. Cross-tenant **POST** → 404 for `pdm_checkin`, `pdm_release`, `pdm_reindex`, `pdv_restore`, `pdv_upload` (plus the smoke's nine); a crafted cross-tenant `document=` POST writes nothing. Empty tenant: 13 GET routes 200, no comment leak. A document with no revisions, a folder with no documents, and a summary-only knowledge entry all render and behave. Pagination `?page=0|-1|abc|99999999|1e5|" 2 "` → 200 everywhere. `?q=` lengths: `pdm_list` sweeps `extracted_text` only from 4 chars (`ZZQ`→0, `ZZQX`→1); `kne_search` has no length rule (`Z`→1). Plain `seed_projects` re-run: **0 media-file delta, 0 row delta** on all six 7.10 tables for both tenants.

**Findings**

**L5-C1 — Critical — `apps/projects/models/DocumentKnowledgeManagement/ProjectFolders.py:142-150`**
`_is_descendant_of()` **can never return `True`**. `seen` is seeded with `self.pk`, and the loop condition `while node is not None and node.pk not in seen` is evaluated **before** `if node.pk == self.pk: return True` — so the walk exits the moment it reaches `self`, and the `return True` is unreachable.
*Exact requests:* `ProjectFolder.full_clean()` on an instance whose `parent` is its own grandchild → **passes, no error**; `A._is_descendant_of(B)` → `False` where B is A's direct child. Through the UI: `POST /projects/doc-folders/<Delta>/edit/` with `parent=<Foxtrot>` (Delta's grandchild) → **302, cycle created, no error shown**; and `GET /projects/doc-folders/<Echo>/edit/` renders `<option value="73">PFD-00006 — Foxtrot</option>` where Foxtrot is Echo's own child, so the dropdown itself offers it.
*Observed state:* with the cycle in place `GET /projects/doc-folders/` rendered **4 rows for 7 existing p1 folders** — the whole cyclic branch vanished with no error and the page showed the ordinary tree; `Echo.full_path` became `'Foxtrot / Delta / Echo'`.
*Why it matters:* the model's `clean()` comment and `Meta` comment assert the invariant, and **lane 1's coverage section and lane 2's contract walk both recorded the cycle guard as enforced** — a false PASS that would have buried this. `_decorate`'s `walk(None, …)` starts from `parent_id is None`, so a cyclic branch is unreachable and silently disappears from the tree. Reachable by an ordinary user picking a descendant from the `<select>`; no data is lost and re-editing the parent recovers it, which is the only reason this is not graded worse.
*Fix:* drop `self.pk` from the initial `seen` (or test equality before the membership check). Also exclude the subtree from the edit form's `parent` queryset (lane 1's L1-M5), and assert both in the `docmgt_*` model lane.

**L5-I1 — Important — `forms/DocumentKnowledgeManagement/ProjectFolders.py:28-45` + `models/…/ProjectFolders.py:106-140`**
A folder that has children can be moved to another project; the children are stranded and no guard exists.
*Exact request:* `POST /projects/doc-folders/<Hotel>/edit/` with `project=<p2>` and an empty `parent` → **302**, `Hotel.project_id = p2`, `India.project_id` stays `p1` with `parent = Hotel`.
*Observed state:* `GET /projects/doc-folders/?project=<p1>` no longer shows `India` at all; `pfd_detail India` still 200. `ProjectFolder.clean()` validates only the moved row's own `parent`/`project` pair, never its children.
*Why it matters:* `ProjectDocumentForm` deliberately disables `project` on edit; the folder form has no equivalent and `project` is a live `<select>`, so one POST grafts a branch across projects and the project lens then hides the stranded children — the same silent-hiding effect as L5-C1 by a second route that is not even claimed to be guarded.
*Fix:* disable `project` on edit in `ProjectFolderForm`, or refuse the move when `self.children.exists()`.

**L5-I2 — Important — `views/DocumentKnowledgeManagement/Documents.py:226-252`**
`pdm_archive`'s un-archive branch guesses the status: `obj.status = "approved" if obj.current_revision_no else "draft"`. The Toggle is not status-neutral.
*Exact requests:* on a document with `status='in_review'`, `current_revision_no=1`: archive then un-archive.
*Observed state:* `in_review`+pointer → `approved`; `superseded`+pointer → `approved`; `in_review`, no pointer → `draft`; only `draft`, no pointer round-trips. A document under review comes back **Approved** with no approval action.
*Why it matters:* `status` drives the register's badge, its `?status=` lens and the repository's `approved` figure, so `pdm_list?status=approved` and `doc_repository` overstate.
*Fix:* stamp the pre-archive status and restore it (a column, or the value already written into the audit row), or refuse to un-archive into a guessed state.

**L5-I3 — Important — `views/DocumentKnowledgeManagement/ProjectFolders.py:59-76` + `:22-55`**
The folder tree's own search cannot find a nested folder.
*Exact requests / observed:* tree `Zulu Root > Yankee Middle > Xray Leaf`, plus root `Whiskey Root`. `?q=Yankee` → **200, 0 rows**, empty state "No folders match"; `?q=Xray` → 0; `?q=Middle` → 0; `?q=Zulu` → 1; `?q=Whiskey` → 1; `?q=Root` → 2. The input's placeholder is "Search folder name or description…".
*Why it matters:* `pfd_list` filters `rows` to the matches and then `_decorate` walks `by_parent` from `parent_id is None`, so any match whose parent was filtered out is never reached — only roots survive. The page then states "Nothing in the tree matches that lens" for a folder that exists, and the count footer is suppressed so nothing contradicts it.
*Fix:* walk each match's `parent_id` chain upward and keep the ancestors as context rows, or search in memory over the whole decorated tree.

**L5-M1 — Minor — `projectdocumentrevision/form.html:28-42` and `projectdocument/detail.html:237-250`**
Both upload surfaces render `form.non_field_errors`, `form.file.errors` and `form.change_note.errors` — never `form.document.errors`, and `document` is a bare hidden input.
*Exact requests / observed:* `POST …/upload/` with `document=<globex pk>` → **200, zero `.form-error` divs, "another workspace" nowhere on the page** (refusal is correct: 0 revisions written); the same with a non-existent pk and with `document` omitted → 200, zero errors. Control: `file=x.exe` renders its error normally.
*Why it matters:* `_reject_foreign` keys the refusal on `document`, so every `document`-field refusal is invisible — the user gets the same form back with no explanation. Only reachable by tampering.
*Fix:* render `{% for e in form.document.errors %}` or convert the failure to a non-field error.

**L5-M2 — Minor — `views/DocumentKnowledgeManagement/Revisions.py:37-71` + `:76-107`**
An **archived** document accepts a new revision and an approval, and stays Archived.
*Exact requests / observed:* archive the document, then `POST …/upload/` → 302, revision added; `POST …/approve/` → 302, pointer moved and the parent's `extracted_text` replaced, while `status` remains `archived` and `is_archived` is True. Neither view nor either form checks `is_archived`; `pdv_approve`'s status lift is gated on `("draft","expected","in_review")` so `archived` is excluded.
*Why it matters:* the register's archive lens and the retention board's `archived` figure still count the row as closed. A record someone archived to freeze silently changes content.
*Fix:* refuse an upload/approval while `is_archived` (or clear the archive on approve, audited).

**L5-M3 — Minor — `views/DocumentKnowledgeManagement/Documents.py:295-318`**
`pdm_reindex`, the verb advertised as the repair, is the second writer that can wipe the search copy.
*Exact requests / observed:* copy `'RECOVERABLE TOKEN TEXT'`; delete the revision's stored file from disk; `POST …/reindex/` → 302 and `extracted_text` becomes `''` with `NOTE_UNREADABLE_PATH`. The document then drops out of the register's 4+-character search.
*Why it matters:* the same "overwrite rather than guard" shape as L1-C1, in the one verb a user presses *because* they suspect the index. A transiently unreachable file permanently destroys a good copy.
*Fix:* when the read returns empty with a note, keep the existing copy and record the note instead of overwriting.

**L5-M4 — Minor — `management/commands/seed_projects.py:285-296`**
`--flush` deletes rows and never touches storage, so a re-seed orphans every 7.10 file.
*Evidence:* the flush block performs no filesystem operation; `_docmgt`'s own docstring warns the block would "quietly pile up duplicate files"; and Django's storage **renames on collision** rather than overwriting — demonstrated live: two uploads named `alpha.txt` produced `alpha.txt` and `alpha_iT29B7Z.txt`. After a flush the rows are gone but the pre-flush files remain, and the re-seed mints new names, leaving the originals unreferenced for ever.
*Why it matters:* the close-out ends with `--flush` + re-seed, so this is not hypothetical — and because `/media/` is served without authentication (note 2 below), the "reset" leaves the previous documents downloadable.
*Fix:* have `--flush` also delete the 7.10 storage subtree, or document explicitly that it does not.

**Deliberate no-action notes**
1. **Upload onto a document under legal hold is accepted (302, file written), but approve and restore are both refused under the hold** — exactly what `ProjectDocumentRevision.clean()` and `pdv_approve` pin, and `detail.html:232` states it. Staging-only upload is the documented posture; not filed.
2. **`/media/` is served with no authentication — a project-wide configuration fact, not a 7.10 defect.** `config/urls.py:22-23` appends `static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)` whenever `DEBUG` is True. Measured in a clean process: `GET /media/projects/documents/2026/09/cart-ui-test-results-r2_39Ps8Th.txt` → **200 / 66 bytes as an anonymous client**, while `GET /projects/documents/<globex pk>/` → 404 for the same actor. 7.10 has **no** download route at all and every one of its views is `@login_required`, so the leak is the handler, not the module. **Routed to security-reviewer:** 7.10 is the module that stores confidential and legally-held payloads in `MEDIA_ROOT`, and `.svg` is on the upload allow-list, so the same handler serves a user-uploaded SVG inline under the site's origin.
3. `pfd_list` has no `?archived=` lens — `?archived=True` is ignored, consistent with lane 4's L4-M3.
4. `pdm_list`'s "Live register" default lens includes archived rows — lane 1's L1-M2, reproduced.
5. `pdv_restore`'s missing checksum → "Different bytes" — lane 1's L1-I1, reproduced.
6. The retention Run re-raises after the reminders are read — lane 2's L2-M1, reproduced.
7. `_docmgt`'s guard is `ProjectFolder.objects.filter(tenant=tenant).exists()`, so a single hand-created folder blocks the whole 7.10 seed for that tenant. Deliberate (the block's entry table is the guard — the house idiom).
8. `pdv_compare` given a document pk returns 200 with the empty state; `pdm_reindex` on a document with no approved revision returns 302 with "nothing to index". Clean.
9. Probe scripts left in `temp/l5_*.py` as evidence; the three orphan media files are the only residue lane 5 could not remove.

### Orchestrator verification of lane 5's Critical (before filing)

**L5-C1 — CONFIRMED, and the mechanism is now pinned exactly.** Re-measured directly:

- `A._is_descendant_of(B)` where B is A's **direct child** → **`False`** (should be `True`).
- `ProjectFolder.full_clean(exclude=["number"])` with `parent` set to the folder's own descendant → **ACCEPTED, no error** (should be `ValidationError` on `parent`).
- The source, read out:
  ```python
  seen, node = {self.pk}, candidate
  while node is not None and node.pk not in seen:
      if node.pk == self.pk:
          return True
      seen.add(node.pk)
      node = node.parent
  return False
  ```
  `seen` is pre-seeded with `self.pk`, so the guard `node.pk not in seen` fires **before** the equality test can: the walk up the ancestor chain terminates precisely when it reaches `self`, and `return True` is unreachable for every input. A correct version seeds `seen = set()` and tests equality first.

**This is a false PASS in the review record, and it is worth naming.** Lane 1's coverage list recorded "descendant-cycle … enforced (`:120-129`)"; lane 2's contract walk marked line 8137 PARTIAL only for the root-duplicate half, implying the cycle half held. Neither had run it. Lane 5's live request is what settled it. The lesson generalises: **a guard whose only evidence is the code that reads it is not verified** — and this is the second time in this review that a lane's confident coverage claim was wrong (the first was lane 1's "only instance repo-wide" for L1-C2).

### Lane 6 — security-reviewer (serial pass 6)

**Scope check.** Read in full: all 5 model modules, all 5 form modules, all 7 view modules, all 8 url modules, the 7.10 admin block (`admin.py:524-588`), the `--flush` block, `config/urls.py`, `config/settings.py` (MIDDLEWARE/TEMPLATES/DEBUG/MEDIA), `apps/core/{crud.py,decorators.py,utils.py,forms/_common.py,models/AuditLog.py}`, `apps/projects/{forms,views}/_common.py`, `views/_helpers.py`, all 22 templates, and the plan. Probed (11 throwaway scripts under `temp/l6_*`): the two forms' field sets and crafted-POST acceptance; `validate_upload` on 9 filename shapes; `file_sha256` rewind; `FileSystemStorage.get_valid_name`/`generate_filename` + Django 5.1.15 `MultiPartParser.sanitize_file_name`; `content_disposition_header` escaping; `django.views.static.serve` on a `.svg`; the real anonymous `/media/` response; template-engine renders of the autoescape filters and of the folder-name `onsubmit` handler (raw attribute **and** `html.unescape()`d, which is what the browser compiles); tenant scoping asserted on every returned **queryset** as `admin_globex`; `pdv_compare` `?a=`/`?b=` with mixed-tenant pks; the check-out-lock form path; and four end-to-end mutations — **every one inside a transaction that was rolled back, each rollback verified**. Verified: 40/40 views `@login_required`, 40/40 POST forms carry `{% csrf_token %}`, 14/14 verbs `@require_POST`, all 40 routes `reverse()`, all 27 mutating call sites write an `AuditLog` row. **Could not verify:** real browser JS execution; an actual anonymous fetch of an uploaded `.svg`; the `pdv_upload` lock bypass end-to-end (proved at form level + code).

**Methodological correction that matters for the record.** Content-matching across tenants is **not** a leak test in this app: `TenantNumbered` gives each tenant its own `PDM-00001…` sequence, so tenant 1's `PDM-00016` and tenant 2's `PDM-00016` are different rows with identical numbers and (seeded) titles. The lane's first sweep reported three false "leaks" on exactly that basis. **Tenant isolation must be asserted on `obj.tenant_id` of the returned rows.**

**Sanity-checks of F-1..F-4 (security angle)**
- **F-1 — PASS.** The whole 7-tuple spec goes to `crud_list`, so the FK lenses pass `as_db_int` + the `0`-is-not-a-pk guard and the queryset is tenant-scoped *before* filtering. Measured as tenant 2: `?project=<t1>`→0 rows, `?folder=<t1>`→0, `?owner=<t1 user>`→0, junk enums ignored, no 500.
- **F-2 — PASS.** `Q(**{f"{field}__icontains": raw})` over a hardcoded 5-field tuple — parameterized, no injection, no field-name control.
- **F-3 — PASS, and load-bearing for authorization, not just UX.** `disabled = True` makes Django read `project` from the instance, so a crafted POST cannot reparent a document. Confirmed: the crafted POST in L6-I2 could set `status` but left `project`/`folder` at the instance's values.
- **F-4 — PASS and complete.** 40/40 route names reverse. The original defect was a `NoReverseMatch`, not an authz hole — nothing was exposed while it was broken.

**Answers to the three routed questions**

**1. Should a legal hold be member-writable? — Split the direction: gate the *release*, keep the *place*.** Measured: `ops_acme` (a plain member) released a hold `admin_acme` had just placed (`302`, `held=False`, `held_by=None`) and then placed one of his own with an arbitrary reason. Both verbs are `@login_required` only, and a hold with an empty reason is accepted. So the "legal hold that BLOCKS" is an annotation any member can attach **and remove**. Recommendation: (a) `pdm_release` → `@tenant_admin_required` (the unfreeze is the sensitive direction; freezing is safe and a member who suspects litigation must still be able to act); (b) require a non-empty `hold_reason` on `pdm_hold`; (c) `detail.html:117` must stop offering Release to non-admins. The in-app precedent is exact — this app already gates `bvr_approve`/`bvr_reject`/`bvr_activate`, `pex_void` and `pko_mark_held`/`pko_complete` with `@tenant_admin_required`. See **L6-I4**.

**2. `/media/` unauthenticated — confirmed as a fact; one correction, and the disposition is *both*.** `config/urls.py:22-23` appends `static(MEDIA_URL, …)` under `DEBUG`; measured an anonymous `200` on `/media/projects/documents/2026/09/baseline-schedule-v3.txt` while `/projects/documents/` is a `302` to `/login/`. **Correction to lane 5's framing:** the response *does* carry `X-Content-Type-Options: nosniff` (from `SecurityMiddleware`) and `Content-Disposition: inline`. So 7.10 inherits a header story — what it lacks is any `Content-Disposition: attachment` story of its own, because it has **no download route at all**. `nosniff` does not help with SVG: the declared type *is* `image/svg+xml`, so a top-level navigation executes the script. Disposition: **project-wide for the auth gap** (one authenticated media view, or nginx `internal`, fixes 14 modules at once) and **7.10-scoped for the type allow-list**, because 7.10 forked the house list and **added `.svg`**, which the house list does not contain. See **L6-C1**.

**3. L5-M4, the data-retention angle — the flush is not the only path; *no* path erases bytes.** Measured: `revision.delete()` removes the row and leaves `revision.file.path` on disk (Django never deletes a `FileField` on row delete); `pdm_delete`, `dtm_delete`, the document/folder cascades and `--flush` (no filesystem call) are the same. Currently **96 files** under `media/projects/documents/` against **46** referencing rows, and **32** under `media/projects/templates/` against **16** — 66 unreferenced payloads the anonymous handler still serves. So "delete" is a UI claim, not an erasure. Recommendation: (a) unlink the stored file inside the delete transaction **reference-counted** — `pdv_restore` deliberately shares a path, so this must not be a bare `instance.file.delete()`; (b) have `--flush` remove the two 7.10 storage subtrees; (c) if erasure really belongs to 13.9/13.14, the delete pages must say so, because `pdm_delete`'s page reads as though the record goes away. See **L6-I6**.

**Confirmations / escalations of lanes 1–5**
- **L3-I2 — CONFIRMED and ESCALATED to Critical.** Lane 3 measured the apostrophe case (renders `Bob&#x27;s` → attribute-decoded to `Bob's` → `SyntaxError`). The same mechanism, with a payload that keeps the injected code *inside* the `confirm(...)` argument list, **executes**: `x',alert(document.cookie),'y` renders `onsubmit="return confirm('Delete folder x&#x27;,alert(document.cookie),&#x27;y? …');"` → the browser compiles `return confirm('Delete folder x',alert(document.cookie),'y? …');` and `alert` is evaluated as an argument. **Measured end-to-end as `ops_acme`** (a plain member): `POST /projects/doc-folders/add/` with that name → `302`, row created, and `GET /projects/doc-folders/` renders **2** handlers carrying the payload. Lane 3's reading of the mechanism is right; only the payload shape in its finding was the dead one. Filed as **L6-C2**.
- **L1-M6 — CONFIRMED and ESCALATED.** `is_archived` is not readonly on `ProjectDocumentAdmin` or `ProjectFolderAdmin` — and the precedent is *in the same file*: `ChannelAdmin` (`:444`) makes exactly those three fields readonly with the identical rationale. The bigger sibling hole is that `ProjectDocumentRevisionAdmin` claims "read-only by construction" but leaves `has_delete_permission` at the default → **delete=True**, so a superuser can delete approved revisions, i.e. the evidence. `TaskBlockAdmin` (`:419-423`) sets `has_delete_permission = False` in this same file for precisely that reason. Filed as **L6-I5**.
- **L1-C2 — CONFIRMED, with the security framing.** Beyond the 500: `AuditLog.action` is a `varchar(10)` whose `choices` `.create()` never validates, so the audit trail's `action` is not a trustworthy column — and the row is unreachable through the register that would surface it, because `auditlog_list` filters on `action` with the enum guard which silently ignores `?action=retention_`, while the detail renders the raw truncated value. The Run is a *control* the board is built around; the 500 is the availability half and the corrupt/unfilterable row is the integrity half.
- **L5-M4 — CONFIRMED and ESCALATED** from a `--flush` note to a module-wide erasure gap (answer 3 / **L6-I6**).
- **L5-C1 — agreed**, with a security-shaped edge: a cycle makes `_decorate`'s `walk(None, …)` drop the whole branch, so a folder and its document list can be made **invisible** to the tree while `pfd_detail` still returns 200. An availability/hiding primitive, not an authz one; not re-filed.
- **Clean claims independently reproduced:** lane 1's 14/14 `@require_POST` and 40/40 `@login_required`; lane 3's 40/40 `{% csrf_token %}`.

**Coverage — clean categories (no findings filed)**
- **Tenant isolation on every read path — CLEAN.** Asserted on the returned queryset as `admin_globex`: `pdm_list` (no lens, `?project=`, `?folder=`, `?q=`, `?owner=`), `pdv_list` (`?document=`, `?project=`), `kne_list` (`?project=`), `pfd_list` (`?project=`) — every row `tenant_id == 2`, every cross-tenant lens narrowing to 0 rows.
- **IDOR on the paths lanes 1–5 did not take — CLEAN.** `pdv_compare` with `?a=<t1>&b=<t2>` resolves the foreign leg to `None` for both actors; the nested `document_pk` is `get_object_or_404(..., tenant=request.tenant)`; `pdm_reindex` and `doc_retention_run` are tenant-scoped; `pdv_upload`'s POSTed `document` cannot redirect the write cross-tenant (`_reject_foreign` refuses it).
- **Upload handling — CLEAN except the allow-list itself.** Path traversal is not reachable: Django 5.1.15's `sanitize_file_name` reduces the part filename to a printable basename, `get_valid_name` strips `"`/`\r\n`/separators, and `generate_filename` raises `SuspiciousFileOperation` for a residual `..`. Double extensions are handled correctly (the **last** extension governs); no extension and `.html` are refused; the 20 MB cap reads `size` and cannot be bypassed by a lying name. `file_sha256` streams via `chunks()` and its `finally: seek(0)` is correct. Content type is **extension-only** (no magic bytes) — documented, and it is why the `.svg` entry is the whole problem.
- **Autoescape / XSS outside the one handler — CLEAN.** No `|safe`, `mark_safe`, `{% autoescape off %}` or inline `<script>` anywhere in the 22 files. Note the premise that `extracted_text` is rendered is wrong: it appears **only** as `|length` — the text itself is never emitted. `body` goes through `|linebreaks`, which escapes first; `tags` render as escaped badges; the reflected `{{ q }}`/`{{ kind_filter }}` are escaped in both text and `value="…"`.
- **CSRF / method hygiene — CLEAN.** 40/40 tokens; 14/14 `@require_POST`; the four delete views mutate only on POST; no `@csrf_exempt`.
- **SQL injection — CLEAN.** ORM only; no `.raw()`, `.extra()`, f-string `cursor.execute`; both hand-written searches parameterize and take field names from literals.
- **Mass assignment — CLEAN for every column but `status`** (L6-I2). Measured: `tenant`, `number`, `current_revision_no`, `extracted_text`, `is_archived`, `is_legal_hold` were all ignored; `usage_count` is off the form; the upload form carries only `document`/`file`/`change_note`.
- **Audit coverage — CLEAN and complete.** All 27 mutating call sites write an `AuditLog` row; no secret or content column is copied (`pdm_reindex` records `chars`/`note`, not the text). The register that reads `changes` is `@tenant_admin_required`, so nothing is disclosed beyond the document page.
- **Secrets / open redirect / clickjacking — CLEAN.** No credential field in any 7.10 form; no `?next=` honouring in 7.10; `XFrameOptionsMiddleware` present.

**Findings**

**L6-C1 — Critical — `models/…/Documents.py:75-78,101-107` + `config/urls.py:22-23`**
7.10 accepts `.svg`, stores it under `MEDIA_ROOT`, and the project serves `MEDIA_ROOT` with no authentication, `Content-Type: image/svg+xml`, `Content-Disposition: inline`.
*Evidence:* (a) `validate_upload(SimpleUploadedFile("evil.svg", b"<svg><script>alert(1)</script></svg>"))` → `None` (accepted); (b) `django.views.static.serve` on a `.svg` → `200`, `Content-Type: image/svg+xml`, `Content-Disposition: inline`, no CSP; (c) the real handler anonymously: `GET /media/projects/documents/2026/09/baseline-schedule-v3.txt` → `200`, `Content-Disposition: inline`, `nosniff`, while `/projects/documents/` → `302 /login/`; (d) 7.10 has no download route of its own. Chain: any member uploads a revision or standard named `*.svg`; any visitor — **including anonymous** — navigates to the media URL and the script runs **under the site origin**, with the app's cookies and CSRF-protected endpoints in reach. `nosniff` is no defence because `image/svg+xml` is the declared type.
*Why it matters:* two harms in one path — stored XSS on the site origin, and 7.10 is the module that stores `classification="confidential"` and legally-held payloads in a world-readable directory. The allow-list is 7.10's own fork of the house list and **adds the one scriptable extension the house list omits**.
*Fix (two halves, both needed):* project-wide — replace `static(MEDIA_URL, …)` with an authenticated download view (or nginx `internal`) so `/media/` is never anonymous; 7.10-scoped — delete `.svg` from `ALLOWED_FILE_EXTENSIONS` (and `.dwg`/`.dxf`, which no browser renders), or serve 7.10 payloads through a 7.10-owned view that sets `Content-Disposition: attachment` and a fixed `application/octet-stream`. Either way, stop defining a second allow-list: extend `core.forms.ALLOWED_DOC_EXTENSIONS` and import it.

**L6-C2 — Critical — `projectfolder/list.html:62,65` and `projectfolder/detail.html:13,98`** (escalation of L3-I2)
The four `onsubmit="return confirm('… {{ row.obj.name }} …')"` handlers interpolate a member-authored folder name into a single-quoted JS literal. Django's autoescaping HTML-escapes the value, but an inline handler's attribute value is **character-reference-decoded before the browser compiles it**, so escaping does not protect this context — and `|escapejs` (absent from all 22 files) is the fix the repo already documents at `procurement/spendanalytics/spendrule/list.html:35,169`.
*Crafted request (measured end-to-end, rolled back):* as `ops_acme` (`is_tenant_admin=False`), `POST /projects/doc-folders/add/` with `name = x',alert(document.cookie),'y` → `302`, row created; `GET /projects/doc-folders/` renders the payload on **both** the archive and the delete handler, which the browser compiles to `return confirm('Delete folder x',alert(document.cookie),'y? …');` — `alert` is evaluated as an argument to `confirm`, i.e. it executes. A same-origin `fetch('/projects/documents/')` payload renders the same way, so the injected code can read and act on any 7.10 page as the viewer.
*Why it matters:* a plain member can execute script in any colleague's session on the folder pages — including a tenant admin's, whose session can reach the audit register and the tenant-admin-gated verbs. The third recurrence of lesson L42's shape and the only XSS sink in the sub-module.
*Fix:* `{{ row.obj.name|escapejs }}` / `{{ obj.name|escapejs }}` at all four sites, and audit the `grep -rn "onsubmit=\"[^\"]*{{" templates/` shape repo-wide.

**L6-I1 — Important — `views/…/Revisions.py:41-51` with `forms/…/Revisions.py:45-56`**
The upload form's check-out refusal authorizes the **POSTed** `document`, but the view then overwrites it with the **URL's** document (`revision.document = locked`). The form is a confused deputy: it validates object B and the write lands on object A.
*Crafted request (measured, rolled back; no file saved):* document A checked out; `ProjectDocumentRevisionUploadForm(data={"document": B.pk, …}, files={…})` → `is_valid() == True`, while the control with `document=A` → `is_valid() == False` (`'That document is checked out by …'`). After `form.save(commit=False)` and `revision.document = locked`, `revision.document_id == A.pk` and `is_locked is True` → **the lock is bypassed**.
*Why it matters:* it defeats the invariant the form's own docstring claims as a second layer ("The lock is refused here, not only in the view"), and it is the one member-reachable way to write a revision onto a document somebody else is editing. No cross-tenant access results, which is why it is not Critical.
*Fix:* ignore the POSTed `document` entirely — drop it from `Meta.fields` and set the initial from the view, or compare `cleaned["document"].pk` against the view's `document_pk` and `add_error` on mismatch.

**L6-I2 — Important — `forms/…/Documents.py:28-31` + `views/…/Documents.py:124-138`**
`status` is on `ProjectDocumentForm`, but two verbs own it (`pdm_archive` sets `archived`, `pdv_approve` lifts `draft/expected/in_review → approved`). A crafted POST can therefore mint a life-cycle claim with no verb behind it.
*Crafted request (measured, rolled back):* on the legally-held `PDM-00017`, `POST /projects/documents/17/edit/` with `status=approved` → `302`, `status='approved'` with `current_revision_no=1` and no approval; then `status=archived` → `302`, `status='archived'` while `is_legal_hold=True` and `is_archived=False`.
*Why it matters:* (a) `status` is what the badge, the `?status=` lens and `doc_repository`'s `approved` figure read, so a member can make a document *report* as approved without evidence — the same overstatement lane 5 found on `pdm_archive`'s un-archive guess, reachable by a second simpler route; (b) it puts the hold's own refusal on the badge path: `clean()` only refuses `is_archived and is_legal_hold`, so a typed `status='archived'` renders "Archived" on a held record without tripping the hold.
*Fix:* take `status` off the form and let the verbs write it. If the plan's "status is a register column" must stand, restrict the field to `("draft","expected","in_review")` and refuse `approved`/`archived` in `clean()`.

**L6-I3 — Important — `views/…/Revisions.py:145-168`**
`pdv_delete`'s only guards are `revision.is_approved` and `revision.revision_no == document.current_revision_no`. There is **no `is_legal_hold` check**, so the hold does not freeze the chain's pending rows.
*Crafted request (measured, rolled back):* on the legally-held `PDM-00017`, mint a pending revision, then `POST /projects/document-revisions/<pk>/delete/` → `302` and **the row is gone**. Rollback verified: the held document's revision count returned to 1.
*Why it matters:* the hold blocks the document delete, the archive, the approve and the restore — but a member can still destroy a staged revision row together with its `checksum`, `uploaded_by`, `change_note` and `approved_by`, and its file stays on disk as an orphan (L6-I6).
*Fix:* add a `document.is_legal_hold` guard beside the existing two, and mirror it in `ProjectDocumentRevision.clean()` the way the approve half already is.

**L6-I4 — Important — all 14 verbs across `{Documents,Revisions,Templates,Knowledge}.py`**
No 7.10 verb carries `@tenant_admin_required`; every one is `@login_required`. Measured: a plain member released the hold `admin_acme` had placed, placed his own, and `pdm_delete`/`pdv_delete`/`pdm_archive`/`pdv_approve`/`kne_publish`/`dtm_publish` are all member-reachable.
*Why it matters:* the plan pins no gate, but the *app* does — this module's siblings gate the approval/void/hold class (`bvr_approve`/`bvr_reject`/`bvr_activate`, `pex_void`, `pko_mark_held`/`pko_complete`). 7.10 introduces an approval verb, two deletes and a legal hold with no gate at all, so the hold is not a control against a member and the evidence-creating act is member-writable.
*Fix:* gate the destructive/approval class — `pdv_approve`, `pdm_delete`, `pdv_delete`, `pdm_archive`, `pdm_release`, `dtm_publish`, `kne_publish` — with `@tenant_admin_required`; keep `pdm_hold` member-open with a required reason; and hide the now-403 buttons in the templates.

**L6-I5 — Important — `admin.py:549-566` (with `:534-546`, `:524-531`)**
`ProjectDocumentRevisionAdmin` documents itself as "read-only by construction (no add, no change)" and sets `has_add_permission`/`has_change_permission` to `False` — but leaves `has_delete_permission` at the default. Measured with a superuser request: `delete=True`. `ModelAdmin.delete_model` is `obj.delete()` with **no `full_clean()`**, and `delete_queryset` is a bulk `queryset.delete()`.
*Why it matters:* a superuser can destroy approved revisions — the rows the module calls evidence, which `pdm_delete`/`pdv_delete` refuse to delete — with no `AuditLog` row and no model validation. The same missing validation means a **legally-held** document can be deleted from `ProjectDocumentAdmin`, because `clean()`'s hold rule is never consulted on the admin delete path. Also confirms lane 1's L1-M6: `is_archived` is writable on both the document and folder admins, while `ChannelAdmin` in the same file makes those three fields readonly with the identical rationale.
*Fix:* `has_delete_permission → False` on `ProjectDocumentRevisionAdmin` (the `TaskBlockAdmin` precedent), add `is_archived`/`archived_by`/`archived_at` to `readonly_fields` on the document and folder admins, and override `has_delete_permission` on `ProjectDocumentAdmin` to refuse a held row.

**L6-I6 — Important — `views/…/Documents.py:161`, `Revisions.py:166`, `Templates.py:84`, `Knowledge.py:135`, `seed_projects.py:285-296`**
No delete path removes the stored bytes. Measured: `revision.delete()` → row gone, `revision.file.path` still present; `--flush` deletes the five 7.10 tables and performs no filesystem operation. The media tree holds 96 files under `projects/documents/` against 46 referencing rows and 32 under `projects/templates/` against 16.
*Why it matters:* combined with L6-C1's anonymous handler, "delete" and "reset the seed" both leave the previous corpus downloadable at its old URL for ever — for a module whose whole point is confidential and legally-held documents, that is a retention failure.
*Fix:* unlink the stored file inside the delete transaction, **reference-counted** (guard the `pdv_restore` shared path); have `--flush` remove the two 7.10 storage subtrees; and if erasure really is 13.9/13.14's, say so on the delete pages, which currently read as an erasure.

**L6-M1 — Minor — `views/…/Documents.py:264`**
`pdm_hold` accepts an empty reason (`(request.POST.get("hold_reason") or "").strip()[:255]`), and the audit row then records `"to": "held"`. Measured: a hold placed with no reason succeeds.
*Why it matters:* the hold is the module's compliance control and its whole value is the recorded basis; `pdm_delete`'s own refusal message has to fall back to "(no reason recorded)", i.e. the control documents its own gap.
*Fix:* refuse an empty `hold_reason` on `pdm_hold`.

**Deliberate no-action notes**
1. **`owner` is exempt from `_reject_foreign`** on all four forms — the documented 7.8/7.9 User-FK exemption, harmless here: a crafted POST can point `owner` at another tenant's user, but `ProjectNotification` reads are tenant-scoped, so the reminder is never delivered across the boundary.
2. **`pdm_checkin` open to any member** — the documented cooperative lock.
3. **Upload onto a legally-held document is accepted** while approve and restore are refused — lane 5's note 1; L6-I3 is the *other* half of that posture.
4. **`pdm_reindex` on a held document** rewrites only the derived search copy — the hold hole there is L5-M3, not the hold.
5. **`pdv_upload` on an archived document is accepted** — lane 5's L5-M2.
6. **`kne_use` / `is_featured` / `is_format_locked`** — click counter / shelf / intent, each documented on the page that shows it.
7. **`pdv_compare` with `?a=`/`?b=`** — both legs tenant-filtered; a document pk renders the empty state. No IDOR.
8. **`RetentionBoard.py:112`'s over-length action** — lane 1's L1-C2; only the security framing is added above.
9. **Probe residue:** five scripts plus one throwaway SVG fixture (`temp/l6_probe_fixture.svg`, 71 B) under gitignored `temp/` — the sandbox blocked the `rm`, so the fixture stays. No app file, media file, or DB row was created: every mutation ran inside a transaction that was rolled back, and each rollback was verified (including the trap where `Model.delete()` nulls `self.pk`, which makes a naive post-rollback `filter(pk=obj.pk)` look like a failed rollback — it is not).

### Orchestrator verification of lane 6's Criticals (before filing)

- **L6-C2 — CONFIRMED, and correctly escalated from Important to Critical.** Rendered the payload through the template engine and read the handler body the browser would compile: `{{ name }}` with `x',alert(document.cookie),'y` → attribute `…confirm('Delete folder x&#x27;,alert(document.cookie),&#x27;y? …');` → after HTML-attribute decoding `…confirm('Delete folder x',alert(document.cookie),'y? …');` — **`alert(document.cookie)` sits in the argument list and is evaluated.** With `|escapejs` the same payload renders `\u0027`, which survives attribute decoding and is inert. So lane 3's mechanism was right and its payload shape was the dead one; lane 6's is live. **Critical.**
- **L6-C1 — CONFIRMED.** `validate_upload(SimpleUploadedFile("evil.svg", …))` → `None` (accepted). The 7.10 allow-list holds **18** extensions against the house `ALLOWED_DOC_EXTENSIONS`' **13**, and the set difference is `['.dwg', '.dxf', '.md', '.ppt', '.pptx', '.svg']` — so 7.10 **forked the list and added `.svg`**, the one scriptable extension the house list deliberately omits. Combined with the measured anonymous `200` on a `MEDIA_ROOT` file, the stored-XSS chain is real. **Critical**, with the fix split project-wide (the anonymous handler) and 7.10-scoped (the allow-list).

---

## Consolidated triage (post-lane-6; deduped, ordered Critical → Important → Minor)

Six lanes, **53 distinct findings** after dedupe: **5 Critical, 22 Important, 26 Minor**. Lane-local ids are mapped to canonical ids; where two lanes found the same thing the later lane's id is merged (noted inline). Severity was re-set where a later lane produced stronger evidence.

**How to read the four already-fixed defects:** F-1..F-4 are **not** in this list — all six lanes sanity-checked them PASS. They are recorded in the header.

### Critical

- [ ] **C1** — `pdv_upload` extracts text from the **raw `UploadedFile`** before `save()`, so `extract_text` cannot read `.path`, the defensive `except` swallows it, and every UI upload stores `extracted_text=""` with a **false** "could not be reached on disk" note; `pdv_approve` then copies that `""` over the parent's search copy. *(= L1-C1; reproduced by lanes 5 and 6.)* **VERIFIED by the orchestrator through a real POST: the parent's 103-char search copy went to 0.** `views/DocumentKnowledgeManagement/Revisions.py:55` → mirror the seeder's order (`save()` → `extract_text(revision.file)` → `save(update_fields=…)`).
- [ ] **C2** — `ProjectFolder._is_descendant_of()` **can never return `True`**: `seen` is pre-seeded with `self.pk`, so the loop's membership guard fires before the equality test and the walk exits exactly when it reaches `self`. The cycle guard is dead, so a folder cycle is creatable through the ordinary edit form, and `_decorate`'s `walk(None, …)` then **silently drops the whole branch** from the tree. *(= L5-C1; refutes lane 1's coverage claim and lane 2's contract-walk line 8137.)* **VERIFIED: `A._is_descendant_of(B)` → `False` for a direct child; `full_clean()` accepts a descendant parent.** `models/…/ProjectFolders.py:142-150` → seed `seen = set()` and test equality first.
- [ ] **C3** — **Stored XSS.** Four `onsubmit="return confirm('… {{ name }} …')"` handlers interpolate a member-authored folder name into a single-quoted JS literal; HTML escaping does **not** protect an inline-handler attribute (it is character-reference-decoded before the browser compiles it), and `|escapejs` is absent from all 22 files. *(= L6-C2, escalating L3-I2 — lane 3's mechanism was right, its payload shape was the dead one.)* **VERIFIED: `x',alert(document.cookie),'y` compiles to `confirm('Delete folder x',alert(document.cookie),'y? …')`.** `projectfolder/list.html:62,65`, `projectfolder/detail.html:13,98` → add `|escapejs` at all four sites (the fix the repo already documents at `procurement/…/spendrule/list.html:169`, lesson **L42** — this is its third recurrence).
- [ ] **C4** — `.svg` is on 7.10's upload allow-list — a **fork** of the house list that adds the one scriptable extension `core.forms.ALLOWED_DOC_EXTENSIONS` deliberately omits — and the project serves `MEDIA_ROOT` **unauthenticated** with `Content-Type: image/svg+xml` and `Content-Disposition: inline`. Any member uploads an `.svg`; any visitor, including anonymous, navigates to it and the script runs on the site origin. The same world-readable directory holds `classification="confidential"` and legally-held payloads. *(= L6-C1.)* **VERIFIED: `validate_upload(evil.svg)` → `None`; the 7.10 list has 18 exts vs the house's 13, delta `['.dwg','.dxf','.md','.ppt','.pptx','.svg']`; an anonymous `GET /media/…/baseline-schedule-v3.txt` → 200.** Fix has **two halves**: 7.10-scoped — drop `.svg` (and `.dwg`/`.dxf`) and stop forking the list; project-wide — replace `static(MEDIA_URL, …)` in `config/urls.py:22-23` with an authenticated download view. **The project-wide half is a cross-module change and must be carried, not silently folded into a 7.10 fix.**
- [ ] **C5** — `doc_retention_run` writes a **23-character** action into `AuditLog.action` (`varchar(10)`), so on this non-strict checkout the row is silently truncated to `retention_` and on a strict-mode server (the MySQL 5.7+/MariaDB 10.2+ default) the insert raises `DataError` and the Run 500s. The corrupt value also makes the column untrustworthy and unfilterable. *(= L1-C2; the lane's "only instance repo-wide" claim was **refuted** — 25 other sites exist, mostly procurement 6.19's.)* **VERIFIED both ways: non-strict stores `'retention_'`; `STRICT_TRANS_TABLES` (session-scoped, rolled back) raises `DataError (1406)`.** `views/…/RetentionBoard.py:112` → `write_audit_log(..., "update", {"verb": "retention_reminders_run", …})`. **Fix 7.10's instance here; carry the repo-wide sweep.**

### Important

- [ ] **I1** — **No 7.10 verb carries `@tenant_admin_required`** (0/14), so a plain member can **release a legal hold** another admin placed, place their own, and delete/approve/archive/publish. The app's own precedent gates exactly this class (`bvr_approve`/`bvr_reject`/`bvr_activate`, `pex_void`, `pko_mark_held`/`pko_complete`). *(= L6-I4, answering lane 1's routed question.)* → gate `pdv_approve`, `pdm_delete`, `pdv_delete`, `pdm_archive`, `pdm_release`, `dtm_publish`, `kne_publish`; keep `pdm_hold` member-open with a **required** reason; hide the now-403 buttons.
- [ ] **I2** — The upload form's check-out refusal authorizes the **POSTed** `document`, but `pdv_upload` then overwrites it with the **URL's** document — a confused deputy, so the lock is bypassable. *(= L6-I1.)* `views/…/Revisions.py:41-51` → drop `document` from the form's `Meta.fields`, or compare and `add_error` on mismatch.
- [ ] **I3** — `status` is on `ProjectDocumentForm` although two verbs own it, so a crafted POST mints `approved`/`archived` with no verb behind it — and a typed `status='archived'` renders "Archived" on a **held** record without tripping the hold's own refusal. *(= L6-I2.)* → take `status` off the form (or restrict it to `draft/expected/in_review` and refuse the rest in `clean()`).
- [ ] **I4** — `pdv_delete` has **no `is_legal_hold` check**, so a member can destroy a staged revision row (checksum, uploader, change note) on a held document. *(= L6-I3.)* → add the guard in the view **and** in `ProjectDocumentRevision.clean()`.
- [ ] **I5** — `ProjectDocumentRevisionAdmin` sets no/change to `False` but leaves `has_delete_permission` at the default, so a superuser can delete **approved revisions** (the evidence) with no `full_clean()` and no audit row; `ProjectDocument.clean()`'s hold rule is never consulted on the admin delete path, so a held document is deletable there too; and `is_archived` is writable on both the document and folder admins, while `ChannelAdmin` in the same file makes those three fields readonly with the identical rationale. *(= L6-I5 + L1-M6 merged.)* → `has_delete_permission = False` (the `TaskBlockAdmin` precedent), add the three archive fields to `readonly_fields`, and refuse a held row in `has_delete_permission`.
- [ ] **I6** — **No delete path removes the stored bytes**: `revision.delete()`, `pdm_delete`, `dtm_delete`, the cascades and `--flush` all leave the file on disk, and the (anonymous) handler keeps serving it. 96 files under `documents/` against 46 referencing rows; 32 under `templates/` against 16. *(= L6-I6, escalating L5-M4.)* → unlink inside the delete transaction **reference-counted** (guard `pdv_restore`'s deliberately shared path); have `--flush` remove the two 7.10 storage subtrees; or state on the delete pages that erasure is 13.9/13.14's.
- [ ] **I7** — A folder **with children** can be moved to another project; the children are stranded and the project lens then hides them. `ProjectFolder.clean()` validates only the moved row's own `parent`/`project` pair. *(= L5-I1.)* → disable `project` on edit (mirroring `ProjectDocumentForm`), or refuse the move when `self.children.exists()`.
- [ ] **I8** — `pdm_archive`'s un-archive **guesses** the status (`"approved" if current_revision_no else "draft"`), so an `in_review` or `superseded` document comes back **Approved** with no approval action — overstating the register, its `?status=` lens and `doc_repository`. *(= L5-I2.)* → stamp the pre-archive status and restore it.
- [ ] **I9** — The folder tree's own **search cannot find a nested folder**: `?q=Yankee` for `Zulu > Yankee > Xray` → 0 rows and "No folders match". The filter keeps only the matches and `_decorate` walks from `parent_id is None`, so any match whose parent was filtered out is unreachable. *(= L5-I3.)* → keep the ancestors as context rows, or search over the decorated tree in memory.
- [ ] **I10** — 7.10 is **invisible on the Projects module landing page** — no stat card, no quick link, no intro mention (7.9 added all three for itself). *(= L2-I1.)* **VERIFIED: 0 occurrences of any 7.10 route in `templates/projects/overview.html`, while 7.9's five are all present.** → mirror the 7.9 block.
- [ ] **I11** — The **root-folder duplicate-name guard only runs on edit** (`and self.pk`), and neither Django nor MySQL covers the create path (a `unique_together` with a NULL is skipped; MySQL treats NULLs as distinct). The invariant is claimed in three places, including `SKILL.md`. *(= L2-I2.)* **VERIFIED: a new duplicate root passes `full_clean()`; renaming an existing one is refused.** → drop `and self.pk`.
- [ ] **I12** — **Review integrity, not a code defect:** the dev DB is no longer in its seeded state (0 pending revisions vs 4; 6 `due_date` notifications the seeder never creates; 13 truncated `retention_` audit rows) because the smoke and the probes press real verbs. *(= L2-I3.)* → the close-out ends with `seed_projects --flush` + `seed_projects`; the header's seeded-shape block describes the **code**, not the live DB.
- [ ] **I13** — `pdv_restore` builds the new revision **without the checksum**, so a byte-identical restore renders "Different bytes" and the sentence that explains a restore sits inside the unreachable `same_checksum` branch. *(= L1-I1.)* → pass `checksum=revision.checksum`.
- [ ] **I14** — `{{ current.approved_by.get_full_name|default:current.approved_by.email }}` is guarded only by `{% if current %}`; `approved_by` is SET_NULL, so deleting the approver makes the document detail page 500. *(= L1-I2; the only unguarded instance of 23.)* → guard the FK.
- [ ] **I15** — `kne_search` paginates with its own `_page()` instead of `crud.paginate()`, and only `crud.paginate` sets `page.window` — so `partials/pagination.html`'s window loop renders **nothing** and the page offers Prev/Next only. *(= L1-I3.)* → use `crud.paginate`, or set `page.window`.
- [ ] **I16** — `{% if obj.extraction_note %}` reads a field that does not exist on `ProjectDocument` (it lives on the revision), so the line is dead markup and the one place a failed text read would surface never renders. *(= L1-I4; compounds C1.)* → read it off `current`.
- [ ] **I17** — `kne_publish` **refuses a retired row**, but both templates render the button unconditionally, so a retired entry shows a "Publish …?" confirm whose promise the server will not keep. *(= L3-I1.)* **VERIFIED: `KNE-00004` is retired, its page renders the Publish form, and the POST leaves the status `retired`.** → wrap in `{% if k.status != 'retired' %}` and show the hint instead.
- [ ] **I18** — The create page instructs that `Expected` is "the one state where a title may be left blank" — but `title` is `blank=False`, so the required-marker sits two lines below the instruction and the instruction cannot be followed. *(= L3-I3, correcting lane 1's no-action note 6.)* → fix the copy and drop the seven dead `|default:"expected placeholder"` branches.
- [ ] **I19** — `_due_rows` pulls **every column of every live document** (including the 200 000-char `extracted_text`) to read two date columns, and the board renders them **unpaginated** (up to 2 rows per document). *(= L4-I1.)* → `.defer("extracted_text")` + `crud.paginate`.
- [ ] **I20** — `kne_search` issues **two byte-identical `COUNT(*)`s** carrying the full 5-field `icontains` sweep (`rows` + `total_count`), doubling the one unindexable operation on the page. *(= L4-I2.)* **VERIFIED: `?q=charter` → 9 queries, 2 COUNTs.** → `"total_count": rows.paginator.count`.
- [ ] **I21** — Four list/detail querysets load a TextField no template on the page reads (`extracted_text` on `pdm_list`/`pfd_detail`/`doc_repository`; `body` on `kne_list`/`kne_search`), and `KnowledgeEntry.body` has **no cap at all**. *(= L4-I3.)* → `.defer(...)` on the five, and a `MaxLengthValidator` on `body`.
- [ ] **I22** — `doc_repository`'s `by_type` loop issues **one COUNT per doc-type choice** — 11 round-trips for one figure, inside a page of 29 queries / 20 COUNTs. *(= L4-I4.)* **VERIFIED: 29 queries, 20 COUNTs.** → one grouped `values().annotate(Count())`.

### Minor

- [ ] **M1** — `LIVE_STATUSES`/`OPEN_STATUSES`/`is_live` have no reader, yet the comment asserts the register and the retention board both use them. *(L1-M1.)*
- [ ] **M2** — The register's archive lens labels its empty value **"Live register"**, but the empty value applies no `is_archived` filter, so archived rows appear under that label. *(L1-M2; lane 3 adds that the retention tile's "live" is a different set.)*
- [ ] **M3** — The claim that a checked-out parent refuses an upload **in the model layer** is stated in three places (the revision docstring, `SKILL.md`, the todo plan); the only implementation is the form. *(L1-M3 + L2-M5.)*
- [ ] **M4** — A **fileless** standard can be created although the plan says the file is required on create and the boundary ruling keeps prose in `KnowledgeEntry`; `_docmgt` itself ships 8 of 16 standards without a file. *(L1-M4.)*
- [ ] **M5** — On edit the folder form's `parent` queryset excludes only `self`, not the subtree, although the plan pins "self + descendants" — the user only learns after submitting. *(L1-M5; the UI half of C2.)*
- [ ] **M6** — `ProjectFolder.status_css` and `ProjectDocumentRevision.is_editable` have no reader. *(L2-M2.)*
- [ ] **M7** — The Run's idempotency is absolute only while the reminders are **unread** (the dedupe key includes `is_read=False`), but the docstring and the page copy state it without that condition. *(L2-M1; reproduced.)*
- [ ] **M8** — `_docmgt`'s docstring says **25 revisions** (two places); the block mints **23**. *(L2-M3; verified.)*
- [ ] **M9** — `DocumentTemplate.document_type` has **no `choices`**, so "the same vocabulary as `ProjectDocument`" is unenforced; and `dtm_list` declares a `document_type` filter **no control sends**. *(L2-M4.)*
- [ ] **M10** — The retention board's own parenthetical names "held rows, archived rows", but only the due rows are rendered — the two states are figures with no list and no lens link. *(L2-M6.)*
- [ ] **M11** — `ProjectDocument.folder`'s comment cites "the 6.19 container rule"; 6.19 has no folder/container concept. *(L2-M7; verified.)*
- [ ] **M12** — `pdv_upload`'s GET page is **orphaned** — no template links to it, so the standalone form is reachable only by typing the URL. *(L3-M1.)*
- [ ] **M13** — The register always offers Edit; the detail page hides it for archived rows; and nothing refuses it — so the two siblings disagree and the server is the one that is permissive. *(L3-M2.)*
- [ ] **M14** — `pdm_delete`'s **"Archive it instead"** button links to the retention board, which has no archive action at all. *(L3-M3.)*
- [ ] **M15** — "leaves the **'start from this' list**" names a list that does not exist; `dtm_detail` states the opposite ruling. *(L3-M4.)*
- [ ] **M16** — The knowledge search empty state prints the **raw** `kind_filter` value ("within the lesson_learned kind"). *(L3-M5.)*
- [ ] **M17** — `pdv_compare`, `kne_detail` and `dtm_detail` have no `select_related` (compare = 15 queries where 2 would do; `kne_detail`/`dtm_detail` 3 FKs each). *(L4-M1.)*
- [ ] **M18** — `pdm_detail`'s `obj.current_revision` is a `.filter()` and so **bypasses the already-loaded `revisions`** — the recorded house class (7.8's 31→13). *(L4-M2.)*
- [ ] **M19** — Index audit: `pfd_tnt_archived_idx` has **no reader**; `classification` and `ProjectDocumentRevision.is_approved` are **unindexed** although each is a live lens. *(L4-M3; verified.)*
- [ ] **M20** — `ancestor_chain()` costs **1 query per ancestor level** and the model imposes **no depth cap**, so a deep chain raises `RecursionError` on `pfd_list`. *(L4-M4.)*
- [ ] **M21** — Two comments measurement contradicts: "the sweep runs **at most once** per page render" (it is twice), and `kne_tnt_feat_idx` "serves the shelf query" (it serves only the filtered facet). *(L4-M5.)*
- [ ] **M22** — `doc_retention_run` opens a `transaction.atomic()` **per row** (~3 statements + 2 transaction round-trips per document). *(L4-M6; code-derived, not measured.)*
- [ ] **M23** — Both upload surfaces render `file`/`change_note`/non-field errors but **never `form.document.errors`**, so every `document`-field refusal is invisible. *(L5-M1.)*
- [ ] **M24** — An **archived** document accepts a new revision and an approval and stays Archived. *(L5-M2.)*
- [ ] **M25** — `pdm_reindex` — the verb advertised as the repair — can **wipe** a good search copy when the file is transiently unreachable. *(L5-M3.)*
- [ ] **M26** — `pdm_hold` accepts an **empty reason**, and the audit row then records `"to": "held"`. *(L6-M1.)*

### Recorded no-action (spec-pinned or deliberate — NOT findings)

| # | Item | Why no action |
|---|---|---|
| N1 | `pfd_list` is unpaginated | Commented in the view and the template: paging a depth-first decorated tree cuts a parent from its children. |
| N2 | `pdv_restore` re-uses the source file object (no copy) | Consistent with "history is never rewritten, never deleted"; only the missing checksum (I13) is a defect. |
| N3 | `pdm_checkin` open to any member | The documented cooperative lock. |
| N4 | Upload onto a **held** document is accepted while approve/restore are refused | The documented staging posture, stated on the detail page. I4 is the other half. |
| N5 | `owner` exempt from `_reject_foreign` on all four forms | The 7.8/7.9 User-FK exemption; notifications are tenant-scoped so nothing crosses. |
| N6 | `DocumentTemplateForm`'s no-op `_reject_foreign(self, cleaned, [])` | Intentional — the register has no tenant-scoped FK — and commented. |
| N7 | `core.Document` untouched; the share register is a read-only lens | The pinned boundary; the route exists and honours `?project=`. |
| N8 | `usage_count` / `is_featured` / `is_format_locked` | Click counter / shelf / intent — every page that shows them says so (all 22 templates read for an enforcement claim; none found). |
| N9 | Retention deletes nothing on a schedule | Stated on four pages; enforcement is 13.9/13.14's. |
| N10 | `pdv_compare` is metadata-only | Says so on the page; redlining is 13.2's. |
| N11 | The nav leaf label is "Folder Tree" where the plan wrote "Folders" | The character-for-character rule applies to the five NavERP.md bullets, which match exactly. |
| N12 | `ProjectDocument.title` `blank=False` vs the unreachable `clean()` branch | Disposition decided: leave the model, fix the copy (I18). |
| N13 | `_docmgt`'s guard is the folder tree | The block's entry table is the guard — the house idiom. |
| N14 | Every 7.10 list `filesort`s | True app-wide (no list indexes its ordering column) → an app-wide pass, not a 7.10 fork. |
| N15 | `/media/` unauthenticated | A project-wide configuration fact, but it is the enabling half of C4 → the project-wide fix is **carried**, not dropped. |
| N16 | The over-length audit action is a repo-wide idiom (25 sites) | C5 fixes 7.10's instance; the sweep is a cross-module change and is **carried**. |
| N17 | `pdm_archive`'s un-archive guess | Filed as I8, not no-action — listed here only because lane 3 originally routed it as a view question. |
| N18 | The `runserver`-only `static(MEDIA_URL, …)` block | DEBUG-only; noted so the C4 fix is not mistaken for a production-only concern. |
