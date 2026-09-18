# Test contract — Projects 7.10 Document & Knowledge Management (`projects`)

> Pinned **before** any test file was written, per the close-out workflow. Every fixture name,
> every hand-computed figure and every assertion target below is decided here first, so the tests
> cannot drift into asserting whatever the code happens to do.
>
> Isolation basis: `pytest.ini` sets `--reuse-db` (schema reuse only). The `db` fixture wraps each
> test in a transaction that is rolled back, so **within one test the database contains only what
> that test's fixtures created** — which is why the figures below can be pinned EXACTLY rather
> than as `>=`. No 7.10 fixture calls `write_audit_log`, so `AuditLog` is empty unless a test
> itself POSTs a verb.

## 1. Fixtures — helpers (`_docmgt_*`, module-private to `conftest.py`)

All helpers follow the `_collab_*` idiom: build the instance, `full_clean(exclude=["number"])`,
`save()`, return it. `number` is minted by `TenantNumbered.save()`, never passed.

| Helper | Signature | Defaults |
|---|---|---|
| `_docmgt_folder` | `(tenant, project, **overrides)` | `name="Governance"`, `parent=None`, `sequence=1`, `is_archived=False` |
| `_docmgt_document` | `(tenant, project, **overrides)` | `title="Charter"`, `document_type="charter"`, `status="draft"`, `folder=None`, `owner=None` |
| `_docmgt_revision` | `(tenant, document, **overrides)` | `file=None` (a `SimpleUploadedFile("r.txt", b"rev body")`), `change_note="Initial upload."`, `is_approved=False` |
| `_docmgt_template` | `(tenant, **overrides)` | `name="Standard template"`, `document_type="charter"`, `category="other"`, `is_active=True`, `is_format_locked=False` |
| `_docmgt_knowledge` | `(tenant, **overrides)` | `title="Lesson learned"`, `kind="lesson_learned"`, `status="draft"`, `category="general"`, `body="What went wrong and why."`, `owner=None` |

## 2. Fixtures — public (`docmgt_*`)

Tenant A actors are the root-conftest `tenant_a` / `admin_user` / `member_user` / `client_a` /
`member_client`; tenant B uses `tenant_b` / `admin_b` / `planning_project_b`. Projects reuse
`planning_project_a` / `planning_project_b` — 7.10 invents no project.

### Tenant A — subjects
| Fixture | Depends on | Shape |
|---|---|---|
| `docmgt_folder_root_a` | `tenant_a`, `planning_project_a` | `parent=None`, `name="Governance"` |
| `docmgt_folder_child_a` | `tenant_a`, `planning_project_a`, `docmgt_folder_root_a` | `parent=root`, `name="Sub-folder"` |
| `docmgt_document_draft_a` | `tenant_a`, `planning_project_a` | `status="draft"`, no revisions |
| `docmgt_document_approved_a` | `tenant_a`, `planning_project_a` | `status="approved"`, `current_revision_no=1`, one approved revision |
| `docmgt_document_archived_a` | `tenant_a`, `planning_project_a` | `is_archived=True`, `status="archived"` |
| `docmgt_document_held_a` | `tenant_a`, `planning_project_a` | `is_legal_hold=True`, `hold_reason="Litigation hold."` |
| `docmgt_revision_pending_a` | `tenant_a`, `docmgt_document_draft_a` | `is_approved=False`, `revision_no=1` |
| `docmgt_revision_approved_a` | `tenant_a`, `docmgt_document_approved_a` | `is_approved=True`, `revision_no=1`, `approved_by=admin_user` |
| `docmgt_template_active_a` | `tenant_a` | `is_active=True`, `is_format_locked=False` |
| `docmgt_template_retired_a` | `tenant_a` | `is_active=False` |
| `docmgt_knowledge_draft_a` | `tenant_a` | `status="draft"`, `is_featured=False` |
| `docmgt_knowledge_published_a` | `tenant_a` | `status="published"`, `is_featured=True` |
| `docmgt_knowledge_retired_a` | `tenant_a` | `status="retired"` |

### Tenant B — 404 subjects
| Fixture | Depends on | Shape |
|---|---|---|
| `docmgt_folder_root_b` | `tenant_b`, `planning_project_b` | `parent=None` |
| `docmgt_document_draft_b` | `tenant_b`, `planning_project_b` | `status="draft"` |
| `docmgt_knowledge_draft_b` | `tenant_b` | `status="draft"` |

## 3. Seeded figures (from `seed_projects` — the figures the smoke asserts)

Per tenant (acme / globex), after a clean seed:

| Table | Count | Notes |
|---|---|---|
| `ProjectFolder` | 12 | 3 roots + 9 children, depth ≤ 2 |
| `ProjectDocument` | 22 | 17 approved, 2 draft, 2 archived, 1 expected placeholder |
| `ProjectDocumentRevision` | 23 | 19 approved, 4 pending |
| `DocumentTemplate` | 16 | 14 active, 2 retired |
| `KnowledgeEntry` | 17 | 8 published, 5 draft, 2 retired, 2 featured |

Cross-tenant: acme's `PDM-00001` is a different row from globex's `PDM-00001`; the number sequence
is per tenant. Every row's `tenant_id` matches its project's tenant.

## 4. Assertion targets — model lane (`test_docmgt_models.py`)

### Numbering
- `ProjectFolder.NUMBER_PREFIX == "PFD"`
- `ProjectDocument.NUMBER_PREFIX == "PDM"`
- `ProjectDocumentRevision` is unnumbered (inherits `TenantOwned`, has no `NUMBER_PREFIX` and no `number`, identified by document number + `revision_no`).
- `DocumentTemplate.NUMBER_PREFIX == "DTM"`
- `KnowledgeEntry.NUMBER_PREFIX == "KNE"`
- No prefix collision with any other model in `apps.projects`.
- Every fixture's `.number` is non-blank and unique per model per tenant.

### `ProjectFolder` constraints
- `_is_descendant_of(child)` → `True` (the cycle guard must be live).
- `full_clean()` with `parent` set to own descendant → `ValidationError` on `parent`.
- `full_clean()` with duplicate root name (same project, `parent=None`) → `ValidationError` on `name`.
- `full_clean()` with `parent` in a different project → `ValidationError` on `parent`.
- `full_path` of root = `name`; of child = `"parent / name"`.

### `ProjectDocument` constraints
- `clean()` with `is_archived=True` and `is_legal_hold=True` → `ValidationError`.
- `clean()` with `status="expected"` and non-empty title → passes.
- `current_revision` returns the approved revision whose `revision_no == current_revision_no`.
- `latest_revision` returns the highest `revision_no` regardless of approval.
- `share_register_url` is a hardcoded path string, not a `reverse()`.

### `ProjectDocumentRevision` constraints
- `revision_no` auto-allocated on save (starts at 1, increments by 1).
- `clean()` with `document.is_legal_hold=True` → `ValidationError`.
- `is_current` is `True` iff `revision_no == document.current_revision_no`.
- `checksum` is computed from `file` content.

### `KnowledgeEntry`
- `clean()` with `status="published"` and empty `title` → `ValidationError`.
- `clean()` with `status="retired"` and `is_featured=True` → `ValidationError`.

## 5. Assertion targets — form lane (`test_docmgt_forms.py`)

### Tenant scoping
- Every FK dropdown (`folder`, `milestone`, `task`, `document`, `project`) contains only the
  fixture's tenant rows.
- A crafted `project=<tenant_b pk>` on a tenant-a form → field error (not a 500).

### Upload validation
- `validate_upload(SimpleUploadedFile("x.exe", b"x"))` returns an error message string (truthy).
- `validate_upload(SimpleUploadedFile("x", b"x"))` returns an error message string (truthy).
- `validate_upload(SimpleUploadedFile("x.svg", b"<svg/>"))` returns an error message string (truthy) (post-C4 fix).
- `validate_upload(SimpleUploadedFile("x.txt", b"x"))` returns `None`.

### Checkout lock
- `ProjectDocumentRevisionUploadForm` with `document.is_checked_out=True` → field error on
  `file`.

### Edit project disabled
- `ProjectDocumentForm` on an instance has `fields["project"].disabled == True`.

## 6. Assertion targets — view lane (`test_docmgt_views.py`)

### Route resolution
All 40 route names reverse (the same list as `smoke_710.py` §Routes).

### GET renders
- Every list page 200s and contains the table header for its entity.
- Every detail page 200s and contains the object's `number`.
- `doc_repository` 200s and contains all six tile labels.
- `doc_retention` 200s and contains "Retention queue".

### Filters
- `pdm_list?q=charter` narrows to 2 rows (seeded).
- `pdm_list?status=draft` narrows to 2 rows.
- `pdm_list?archived=True` narrows to 2 rows.
- `kne_search?q=retro` narrows to 2 rows.
- `kne_search?kind=lesson_learned` narrows to 9 rows.
- Junk `?status=nope` is ignored (returns full list, 200).

### Pagination
- `pdm_list` page 1 has 15 rows, page 2 has 7, page 99999 is safe.
- `pfd_list` is NOT paginated (no `page_obj` in context).

### POST verbs
- `pdv_approve` on a pending revision → `status="approved"`, pointer moved, audit row with
  `changes["verb"] == "revision_approve"`.
- `pdm_archive` → `is_archived=True`, `status="archived"`.
- `pdm_unarchive` (POST to archive on an already-archived doc) → `is_archived=False`.
- `pdm_hold` → `is_legal_hold=True`, `hold_reason` recorded.
- `pdm_release` → `is_legal_hold=False`.
- `pdm_checkout` → `is_checked_out=True`, `checked_out_by=admin_user`.
- `pdm_checkin` → `is_checked_out=False`.
- `kne_publish` on draft → `status="published"`.
- `kne_publish` on published → `status="draft"`.
- `kne_publish` on retired → status unchanged, flash message.

### Empty states
- A tenant with no documents: `pdm_list` 200s and contains "No documents match that lens."
- A tenant with no folders: `pfd_list` 200s and contains "No folders."

## 7. Assertion targets — security lane (`test_docmgt_security.py`)

### Anonymous
- Every 7.10 GET route → 302 to `/login/` (or 302 from `@login_required`).
- Every 7.10 POST route → 302 to `/login/`.

### POST-only verbs
- GET on every `@require_POST` verb (`pdv_approve`, `pdv_delete`, `pdv_restore`, `pdm_archive`,
  `pdm_hold`, `pdm_release`, `pdm_checkout`, `pdm_checkin`, `pdm_reindex`, `pdm_delete`,
  `kne_publish`, `kne_use`, `kne_delete`, `dtm_publish`) → 405.

### Cross-tenant
- `client_a` GET `pdm_detail` with `pk=docmgt_document_draft_b.pk` → 404.
- `client_a` POST `pdv_approve` with `pk=docmgt_revision_pending_b.pk` → 404.
- `client_a` POST `pdm_archive` with `pk=docmgt_document_draft_b.pk` → 404.
- `client_a` GET `kne_detail` with `pk=docmgt_knowledge_draft_b.pk` → 404.

### Mass assignment
- Crafted POST to `pdm_edit` with `tenant=<tenant_b pk>` → tenant unchanged.
- Crafted POST with `number="FORGED"` → number unchanged.
- Crafted POST with `current_revision_no=99` → unchanged.

### XSS context
- `projectfolder/list.html` with a folder named `x',alert(1),'y` renders the payload inside
  `confirm(...)` but `|escapejs` makes it a string argument, not code.

## 8. Post-fix gates (C1–C5, I1–I22, M1–M26 verified invariants)

| Gate | Target / Invariant |
|---|---|
| C1 | `pdv_upload` populates `extracted_text` from saved `FieldFile` and `extraction_note` is empty for plain-text; `pdv_approve` preserves valid search text |
| C2 | `ProjectFolder._is_descendant_of(child)` returns `True`; cycle detection in `clean()` rejects descendant parent |
| C3 | Folder list and detail confirm handlers use `|escapejs` to prevent inline JS attribute breakout |
| C4 | Upload validator uses core doc extension allow-list with `.md`, `.ppt`, `.pptx`; rejects `.svg`, `.dwg`, `.dxf` |
| C5 | Retention run writes audit action `'update'` with verb in `changes`, avoiding 10-char column truncation |
| I1 | Verb endpoints enforce role boundaries (`@tenant_admin_required` for approvals/deletes/releases); member gets 403, admin gets 302 |
| I2 | Revision upload checks locked state against the URL document, not an arbitrary POSTed document |
| I3 | `ProjectDocumentForm` permits only draft/expected/in_review on create; excludes unverified approved/archived claims |
| I4 | Pending revision on a legally held document cannot be deleted via `pdv_delete` or model delete |
| I5 | `ProjectDocumentRevisionAdmin` has `has_delete_permission = False`; held documents cannot be deleted via admin |
| I6 | Deleting documents/revisions purges stored file bytes with reference counting; `--flush` clears storage subtrees |
| I7 | `ProjectFolderForm` disables `project` on edit; cannot move folder with children/documents across projects |
| I8 | `pdm_archive` unarchive restores `pre_archive_status` rather than guessing |
| I9 | `pfd_list` tree search includes ancestor path for matching child folders |
| I10 | `projects/overview.html` includes 7.10 KPI tiles and quick-link destinations |
| I11 | Creating a new duplicate root folder name in the same project raises `ValidationError` on `name` |
| I12 | Dev database drift documented; seeder creates canonical shapes |
| I13 | `pdv_restore` carries forward source checksum; `pdv_compare` identifies identical bytes |
| I14 | `projectdocument/detail.html` safely handles null `approved_by` without `VariableDoesNotExist` 500 |
| I15 | `kne_search` paginator sets `page.window` for numerical pagination links |
| I16 | `projectdocument/detail.html` reads `extraction_note` from current revision |
| I17 | Retired knowledge entries render status hint instead of broken publish form |
| I18 | Copy corrected: expected placeholder requires title; dead blank title fallbacks removed |
| I19 | Retention queue defers `extracted_text` and paginates |
| I20 | `kne_search` uses single COUNT query via paginator count |
| I21 | Five text-heavy querysets defer unused TextFields (`extracted_text`, `body`); `KnowledgeEntry.body` capped |
| I22 | `doc_repository` aggregates doc types in single query with `Count("id")` |
| M1–M26 | Minor consistency, dead-code cleanup, template label fixes, and query optimizations |

## 9. Gate

Run tests using pytest within the virtual environment:
```powershell
.\venv\Scripts\pytest.exe apps/projects/tests/test_docmgt_models.py apps/projects/tests/test_docmgt_forms.py apps/projects/tests/test_docmgt_views.py apps/projects/tests/test_docmgt_security.py -v --nomigrations
```
All four modules must pass 100% green with zero failures.
