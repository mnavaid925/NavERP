# Consolidated Review Findings — Sub-module 13.1: Document Creation & Authoring (Module 13: Document Management System, `documents`)

**Changeset**: `046eecb0bbea97d5200c85f8c7a5b81eae74aa9b...HEAD`
**Target App**: `apps/documents/` (Sub-module 13.1: `DocumentAuthoring`)
**Reviewers**: `code-reviewer`, `explorer`, `frontend-reviewer`, `performance-reviewer`, `qa-smoke-tester`, `security-reviewer`
**Status**: 100% Burned Down (All 27 items fixed and verified clean).

---

## Critical Findings (C1 – C8)

- [x] **C1** | `apps/documents/views/DocumentAuthoring/DocumentDrafts.py:240-244` — TypeError on Document Promotion (`draft_promote`): `core.Document.objects.create(tenant=request.tenant, title=draft.title, description=...)` crashes with `TypeError: Document() got unexpected keyword argument(s) 'title', 'description'`. `core.Document` defines `name`, `file`, `classification`, `version`. In addition, `core.Document.file` is non-nullable.
  - *Fix*: Create `core.Document` with `name=draft.title`, `file=ContentFile(draft.content.encode('utf-8'), name=f"{draft.number}.html")`, and `classification="sop"` (or matching type).
  - *Status*: [x] fixed — `fix(documents): correct core.Document creation parameters and file in draft_promote` (`e388c6f8`)

- [x] **C2** | `apps/documents/views/DocumentAuthoring/TemplateSections.py:22`, `DocumentDrafts.py:25`, `DraftCollaborations.py:24` — Function-call syntax `Q(field__icontains(q))` instead of keyword argument syntax `Q(field__icontains=q)` raises `NameError: name 'title__icontains' is not defined` whenever search query `?q=` is supplied.
  - *Fix*: Replace with `Q(title__icontains=q) | Q(number__icontains=q) | Q(content__icontains=q)` across all 3 list views.
  - *Status*: [x] fixed — `fix(documents): use keyword argument syntax in Q search filter for template sections` (`52e5c19b`), `fix(documents): use keyword argument syntax in Q search filter for document drafts` (`30fe5e1b`), `fix(documents): use keyword argument syntax in Q search filter for draft collaborations` (`b5d13090`)

- [x] **C3** | `templates/documents/document_authoring/document_template/detail.html:139` — Chained default lookup `{{ template.owner.get_full_name|default:template.owner.username|default:"Unassigned" }}` crashes with `VariableDoesNotExist` (HTTP 500) when `template.owner = None` (Lesson L10).
  - *Fix*: Wrap with `{% if template.owner %}{{ template.owner.get_full_name|default:template.owner.username }}{% else %}Unassigned{% endif %}`. Apply defensive check across sibling user lookups.
  - *Status*: [x] fixed — `fix(documents): safely handle null template owner on template detail` (`b70c9e32`)

- [x] **C4** | `apps/documents/forms/DocumentAuthoring/DocumentTemplates.py:64-65` — `DocumentTemplateForm.__init__` scopes `target_org_unit` to `self.tenant`, but omits filtering `self.fields["owner"].queryset`. Leaks cross-tenant users into the form dropdown.
  - *Fix*: Filter `self.fields["owner"].queryset = User.objects.filter(tenant=self.tenant).order_by("username")` and add tenant clean guard in `DocumentTemplate.clean()`.
  - *Status*: [x] fixed — `fix(documents): add owner tenant isolation validation to DocumentTemplate.clean` (`87b16441`), `fix(documents): scope DocumentTemplateForm owner queryset to tenant` (`3ac12bf6`), `fix(documents): use get_user_model for DocumentTemplateForm owner queryset` (`f706f1bd`)

- [x] **C5** | `apps/documents/views/DocumentAuthoring/DocumentDrafts.py:236` — `draft_promote` lacks idempotency and status checks. Re-promoting creates duplicate orphaned `core.Document` rows, and discarded/conflict-pending drafts can be promoted.
  - *Fix*: Add guards checking `draft.status == "promoted"`, `draft.status == "discarded"`, and `draft.sync_status == "conflict_pending"`.
  - *Status*: [x] fixed — `fix(documents): add status and sync conflict guards in draft_promote` (`8112773b`)

- [x] **C6** | `apps/documents/views/DocumentAuthoring/DraftCollaborations.py:147` — `collaboration_resolve` does not verify `collaboration.status == "open"` prior to applying text replacements. Duplicate submissions re-replace text across `draft.content` and modify resolved entries.
  - *Fix*: Assert `collaboration.status == "open"` and validate `action in ("accept", "reject", "resolve")`.
  - *Status*: [x] fixed — `fix(documents): assert open status and valid action in collaboration_resolve` (`b877bc1b`)

- [x] **C7** | `apps/documents/views/DocumentAuthoring/DocumentDrafts.py:154-157` & `templates/documents/document_authoring/document_draft/canvas.html:97` — 1 + N N+1 queries in Canvas View due to prefetch cache invalidation: calling `.filter(status="open")` invalidates prefetched `collaborations__author` cache, firing N separate queries for `c.author`.
  - *Fix*: Filter in Python `[c for c in draft.collaborations.all() if c.status == "open"]` or query with `select_related("author")`.
  - *Status*: [x] fixed — `fix(documents): avoid prefetch cache invalidation for open collaborations in draft_canvas` (`784d3e8b`), `fix(documents): use length filter for open collaborations list count on canvas` (`d5abbf8b`)

- [x] **C8** | `apps/documents/views/DocumentAuthoring/DocumentDrafts.py:66-68` & `templates/documents/document_authoring/document_draft/detail.html:115` — 1 + N N+1 queries in Draft Detail View due to redundant `.order_by("-created_at")` invalidating prefetched `collaborations` cache.
  - *Fix*: Use `draft.collaborations.all()` directly relying on model Meta ordering.
  - *Status*: [x] fixed — `fix(documents): rely on model Meta ordering to preserve prefetch cache in draft_detail` (`1fccc1eb`)

---

## Important Findings (I1 – I12)

- [x] **I1** | `apps/documents/views/DocumentAuthoring/DocumentDrafts.py:109, 173` — Missing lock & lifecycle mutation guards in `draft_autosave` and `draft_edit`: when `draft.is_collaboration_locked` or `draft.status in ("promoted", "discarded")`, edits and autosaves continue mutating content.
  - *Fix*: Return error/423 in autosave and validation error in edit form when locked or promoted/discarded.
  - *Status*: [x] fixed — `fix(documents): add lock and lifecycle mutation guards in draft_edit and draft_autosave` (`8e69f5f6`), `fix(documents): add status validation in DocumentDraftForm.clean` (`a2c409c6`)

- [x] **I2** | `apps/documents/views/DocumentAuthoring/DocumentTemplates.py:108, 134` & `TemplateSections.py:98, 124` — Bypass of structural formatting lock (`is_locked`) on templates and sections by non-admin users.
  - *Fix*: Guard edits and deletes on locked items to require `is_tenant_admin`.
  - *Status*: [x] fixed — `fix(documents): require tenant admin privileges to edit or delete locked templates` (`a0ce229c`), `fix(documents): require tenant admin privileges to edit or delete locked template sections` (`09c0d50f`)

- [x] **I3** | `apps/documents/views/DocumentAuthoring/DraftCollaborations.py:108, 135` — Missing ownership authorization on editing/deleting collaboration notes: any user in tenant can edit/delete notes authored by others.
  - *Fix*: Require `collaboration.author == request.user or request.user.is_tenant_admin`.
  - *Status*: [x] fixed — `security(documents): enforce author permission check in collaboration_edit` (`cb3b0e9c`), `fix(documents): add permission check, select_related, and pagination fixes to DraftCollaborations` (`251ab00d`)

- [x] **I4** | `templates/documents/document_authoring/document_draft/canvas.html:43-51` — Undefined `formatDoc()` function in Canvas toolbar causes `ReferenceError`.
  - *Fix*: Implement selection-range text replacement in canvas JS.
  - *Status*: [x] fixed — `fix(documents): add formatDoc helper, token escaping, and live word count to canvas` (`3f99463b`)

- [x] **I5** | `templates/documents/document_authoring/draft_collaboration/detail.html:29-53` — Missing POST Delete action and Back-to-List button on Collaboration detail page.
  - *Fix*: Add POST delete form and back button to `page-actions`.
  - *Status*: [x] fixed — `feat(documents): add delete action and back-to-list button in collaboration detail` (`d49d2a91`)

- [x] **I6** | `templates/documents/document_authoring/document_draft/canvas.html:80, 127` — Missing `|escapejs` on `insertToken('{{ key|escapejs }}')`, and word count is only updated after server autosave roundtrip instead of live on input.
  - *Fix*: Add `|escapejs` and live client-side word count update on `input`.
  - *Status*: [x] fixed — `fix(documents): add formatDoc helper, token escaping, and live word count to canvas` (`3f99463b`)

- [x] **I7** | `apps/documents/views/DocumentAuthoring/DocumentTemplates.py:65-68` — Wasted prefetch query and cache bypass in `template_detail`: `derived_drafts` prefetch is wasted (only count is rendered), and `.order_by("order", "id")` invalidates `sections` cache.
  - *Fix*: Remove `derived_drafts` from prefetch and use `template.sections.all()`.
  - *Status*: [x] fixed — `perf(documents): defer content in template_list, optimize prefetch in template_detail, and populate word_count in instantiate` (`a2962206`)

- [x] **I8** | `apps/documents/views/DocumentAuthoring/TemplateSections.py:99, 125` & `DraftCollaborations.py:136` — Chained lazy FK traversal in audit logging via `__str__` (Lesson L18): `TemplateSection.__str__` accesses `self.template.name` and `DraftCollaboration.__str__` accesses `self.draft.number`.
  - *Fix*: Pass `select_related` to `documents_object` in edit and delete views.
  - *Status*: [x] fixed — `perf(documents): optimize template choices, add select_related for audit log, and standardize pagination in TemplateSections` (`f9bb23e6`), `fix(documents): add permission check, select_related, and pagination fixes to DraftCollaborations` (`251ab00d`)

- [x] **I9** | `apps/documents/views/DocumentAuthoring/DocumentDrafts.py:21`, `DocumentTemplates.py:19`, `DraftCollaborations.py:20` — Heavy TextFields fetched on list views.
  - *Fix*: Use `.defer("content", ...)` on list views.
  - *Status*: [x] fixed — `perf(documents): defer content and eliminate redundant count query in draft_list` (`08325118`), `perf(documents): defer content in template_list, optimize prefetch in template_detail, and populate word_count in instantiate` (`a2962206`)

- [x] **I10** | `apps/documents/views/DocumentAuthoring/TemplateSections.py:37` & form choice querysets — Unconstrained full table scans for dropdown querysets loading unused text fields.
  - *Fix*: Use `.only("id", "name", "number")`.
  - *Status*: [x] fixed — `perf(documents): optimize template choices, add select_related for audit log, and standardize pagination in TemplateSections` (`f9bb23e6`), `perf(documents): optimize template queryset with only id, name, number in TemplateSectionForm` (`9a76e5a8`), `perf(documents): optimize foreign key querysets with only in DocumentDraftForm` (`7260212c`)

- [x] **I11** | `apps/documents/views/_common.py:26` — Fragile custom queryset tenant filtering in `documents_object`.
  - *Fix*: Ensure `base.filter(tenant=request.tenant)` is always enforced even if custom queryset is passed.
  - *Status*: [x] fixed — `security(documents): enforce tenant filtering unconditionally in documents_object` (`e05f6c42`)

- [x] **I12** | `apps/documents/admin.py:1` — `DraftCollaboration` model is omitted from admin model registrations, leaving it without administrative visibility.
  - *Fix*: Import and register `DraftCollaboration` in `apps/documents/admin.py`.
  - *Status*: [x] fixed — `admin(documents): register DraftCollaboration model in admin site` (`8afb2e3b`)

---

## Minor Findings (M1 – M7)

- [x] **M1** | `apps/documents/views/DocumentAuthoring/DocumentTemplates.py:10` — Unused import `from apps.core.decorators import tenant_admin_required`.
  - *Fix*: Remove unused import.
  - *Status*: [x] fixed — `perf(documents): defer content in template_list, optimize prefetch in template_detail, and populate word_count in instantiate` (`a2962206`)

- [x] **M2** | `apps/documents/views/DocumentAuthoring/DocumentTemplates.py:151` — `template_instantiate` sets `content=template.content` but does not populate `draft.word_count`.
  - *Fix*: Set `word_count=count_words(template.content)`.
  - *Status*: [x] fixed — `perf(documents): defer content in template_list, optimize prefetch in template_detail, and populate word_count in instantiate` (`a2962206`)

- [x] **M3** | `apps/documents/views/DocumentAuthoring/*.py` — Redundant dual `COUNT(*)` query in list pagination.
  - *Fix*: Construct `paginator = Paginator(qs, 15)` first, then use `total_count = paginator.count`.
  - *Status*: [x] fixed — `perf(documents): defer content and eliminate redundant count query in draft_list` (`08325118`), `perf(documents): defer content in template_list, optimize prefetch in template_detail, and populate word_count in instantiate` (`a2962206`), `fix(documents): add permission check, select_related, and pagination fixes to DraftCollaborations` (`251ab00d`), `perf(documents): optimize template choices, add select_related for audit log, and standardize pagination in TemplateSections` (`f9bb23e6`)

- [x] **M4** | `apps/documents/views/DocumentAuthoring/TemplateSections.py:33` & `DraftCollaborations.py:35` — Non-standard page size (20 vs NavERP standard 15).
  - *Fix*: Standardize `Paginator(qs, 15)`.
  - *Status*: [x] fixed — `fix(documents): add permission check, select_related, and pagination fixes to DraftCollaborations` (`251ab00d`), `perf(documents): optimize template choices, add select_related for audit log, and standardize pagination in TemplateSections` (`f9bb23e6`)

- [x] **M5** | `apps/documents/views/DocumentAuthoring/DraftCollaborations.py:142` — `collaboration_delete` redirects unconditionally to `documents:draft_detail`, which disrupts navigation when an admin deletes a record directly from `documents:collaboration_list`.
  - *Fix*: Redirect to `documents:collaboration_list` if requested from list.
  - *Status*: [x] fixed — `fix(documents): add permission check, select_related, and pagination fixes to DraftCollaborations` (`251ab00d`)

- [x] **M6** | `templates/documents/document_authoring/*/list.html` — Missing `for` / `id` attribute coupling on filter form labels and inputs.
  - *Fix*: Add matching `for` and `id` attributes.
  - *Status*: [x] fixed — `fix(documents): couple label for and input id in template list filter form` (`f53c4ef9`), `fix(documents): couple label for and input id in template section list filter form` (`d6c6ef70`), `fix(documents): couple label for and input id in draft list filter form` (`cfa92370`), `fix(documents): couple label for and input id in collaboration list filter form` (`f1ac2a45`)

- [x] **M7** | `apps/documents/models/DocumentAuthoring/DocumentDrafts.py:96-102` & `TemplateSections.py:39-45` — Missing composite index on `(tenant, -updated_at)` on DocumentDraft and `(tenant, template, order)` on TemplateSection.
  - *Fix*: Add indexes in models and generate migration.
  - *Status*: [x] fixed — `perf(documents): add composite index on tenant and updated_at to DocumentDraft` (`43bdfe6a`), `perf(documents): add composite index on tenant, template, and order to TemplateSection` (`1679dcaf`), `chore(documents): add migration 0003 for composite indexes on DocumentDraft and TemplateSection` (`39cd0b9c`)
