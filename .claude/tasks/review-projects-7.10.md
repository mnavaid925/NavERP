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
