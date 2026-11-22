# Consolidated Review Findings — Sub-module 13.1: Document Creation & Authoring (Module 13: Document Management System, `documents`)

**Changeset**: `046eecb0bbea97d5200c85f8c7a5b81eae74aa9b...HEAD`
**Target App**: `apps/documents/` (Sub-module 13.1: `DocumentAuthoring`)
**Reviewers**: `code-reviewer`, `explorer`, `frontend-reviewer`, `performance-reviewer`, `qa-smoke-tester`, `security-reviewer`
**Status**: Deduplicated, prioritized, and ready for `code-fixer` burn-down.

---

## Critical Findings (C1 – C8)

- [ ] **C1** | `apps/documents/views/DocumentAuthoring/DocumentDrafts.py:240-244` — TypeError on Document Promotion (`draft_promote`): `core.Document.objects.create(tenant=request.tenant, title=draft.title, description=...)` crashes with `TypeError: Document() got unexpected keyword argument(s) 'title', 'description'`. `core.Document` defines `name`, `file`, `classification`, `version`. In addition, `core.Document.file` is non-nullable.
  - *Fix*: Create `core.Document` with `name=draft.title`, `file=ContentFile(draft.content.encode('utf-8'), name=f"{draft.number}.html")`, and `classification="sop"` (or matching type).

- [ ] **C2** | `apps/documents/views/DocumentAuthoring/TemplateSections.py:22`, `DocumentDrafts.py:25`, `DraftCollaborations.py:24` — Function-call syntax `Q(field__icontains(q))` instead of keyword argument syntax `Q(field__icontains=q)` raises `NameError: name 'title__icontains' is not defined` whenever search query `?q=` is supplied.
  - *Fix*: Replace with `Q(title__icontains=q) | Q(number__icontains=q) | Q(content__icontains=q)` across all 3 list views.

- [ ] **C3** | `templates/documents/document_authoring/document_template/detail.html:139` — Chained default lookup `{{ template.owner.get_full_name|default:template.owner.username|default:"Unassigned" }}` crashes with `VariableDoesNotExist` (HTTP 500) when `template.owner = None` (Lesson L10).
  - *Fix*: Wrap with `{% if template.owner %}{{ template.owner.get_full_name|default:template.owner.username }}{% else %}Unassigned{% endif %}`. Apply defensive check across sibling user lookups.

- [ ] **C4** | `apps/documents/forms/DocumentAuthoring/DocumentTemplates.py:64-65` — `DocumentTemplateForm.__init__` scopes `target_org_unit` to `self.tenant`, but omits filtering `self.fields["owner"].queryset`. Leaks cross-tenant users into the form dropdown.
  - *Fix*: Filter `self.fields["owner"].queryset = User.objects.filter(tenant=self.tenant).order_by("username")` and add tenant clean guard in `DocumentTemplate.clean()`.

- [ ] **C5** | `apps/documents/views/DocumentAuthoring/DocumentDrafts.py:236` — `draft_promote` lacks idempotency and status checks. Re-promoting creates duplicate orphaned `core.Document` rows, and discarded/conflict-pending drafts can be promoted.
  - *Fix*: Add guards checking `draft.status == "promoted"`, `draft.status == "discarded"`, and `draft.sync_status == "conflict_pending"`.

- [ ] **C6** | `apps/documents/views/DocumentAuthoring/DraftCollaborations.py:147` — `collaboration_resolve` does not verify `collaboration.status == "open"` prior to applying text replacements. Duplicate submissions re-replace text across `draft.content` and modify resolved entries.
  - *Fix*: Assert `collaboration.status == "open"` and validate `action in ("accept", "reject", "resolve")`.

- [ ] **C7** | `apps/documents/views/DocumentAuthoring/DocumentDrafts.py:154-157` & `templates/documents/document_authoring/document_draft/canvas.html:97` — 1 + N N+1 queries in Canvas View due to prefetch cache invalidation: calling `.filter(status="open")` invalidates prefetched `collaborations__author` cache, firing N separate queries for `c.author`.
  - *Fix*: Filter in Python `[c for c in draft.collaborations.all() if c.status == "open"]` or query with `select_related("author")`.

- [ ] **C8** | `apps/documents/views/DocumentAuthoring/DocumentDrafts.py:66-68` & `templates/documents/document_authoring/document_draft/detail.html:115` — 1 + N N+1 queries in Draft Detail View due to redundant `.order_by("-created_at")` invalidating prefetched `collaborations` cache.
  - *Fix*: Use `draft.collaborations.all()` directly relying on model Meta ordering.

---

## Important Findings (I1 – I12)

- [ ] **I1** | `apps/documents/views/DocumentAuthoring/DocumentDrafts.py:109, 173` — Missing lock & lifecycle mutation guards in `draft_autosave` and `draft_edit`: when `draft.is_collaboration_locked` or `draft.status in ("promoted", "discarded")`, edits and autosaves continue mutating content.
  - *Fix*: Return error/423 in autosave and validation error in edit form when locked or promoted/discarded.

- [ ] **I2** | `apps/documents/views/DocumentAuthoring/DocumentTemplates.py:108, 134` & `TemplateSections.py:98, 124` — Bypass of structural formatting lock (`is_locked`) on templates and sections by non-admin users.
  - *Fix*: Guard edits and deletes on locked items to require `is_tenant_admin`.

- [ ] **I3** | `apps/documents/views/DocumentAuthoring/DraftCollaborations.py:108, 135` — Missing ownership authorization on editing/deleting collaboration notes: any user in tenant can edit/delete notes authored by others.
  - *Fix*: Require `collaboration.author == request.user or request.user.is_tenant_admin`.

- [ ] **I4** | `templates/documents/document_authoring/document_draft/canvas.html:43-51` — Undefined `formatDoc()` function in Canvas toolbar causes `ReferenceError`.
  - *Fix*: Implement selection-range text replacement in canvas JS.

- [ ] **I5** | `templates/documents/document_authoring/draft_collaboration/detail.html:29-53` — Missing POST Delete action and Back-to-List button on Collaboration detail page.
  - *Fix*: Add POST delete form and back button to `page-actions`.

- [ ] **I6** | `templates/documents/document_authoring/document_draft/canvas.html:80, 127` — Missing `|escapejs` on `insertToken('{{ key|escapejs }}')`, and word count is only updated after server autosave roundtrip instead of live on input.
  - *Fix*: Add `|escapejs` and live client-side word count update on `input`.

- [ ] **I7** | `apps/documents/views/DocumentAuthoring/DocumentTemplates.py:65-68` — Wasted prefetch query and cache bypass in `template_detail`: `derived_drafts` prefetch is wasted (only count is rendered), and `.order_by("order", "id")` invalidates `sections` cache.
  - *Fix*: Remove `derived_drafts` from prefetch and use `template.sections.all()`.

- [ ] **I8** | `apps/documents/views/DocumentAuthoring/TemplateSections.py:99, 125` & `DraftCollaborations.py:136` — Chained lazy FK traversal in audit logging via `__str__` (Lesson L18): `TemplateSection.__str__` accesses `self.template.name` and `DraftCollaboration.__str__` accesses `self.draft.number`.
  - *Fix*: Pass `select_related` to `documents_object` in edit and delete views.

- [ ] **I9** | `apps/documents/views/DocumentAuthoring/DocumentDrafts.py:21`, `DocumentTemplates.py:19`, `DraftCollaborations.py:20` — Heavy TextFields fetched on list views.
  - *Fix*: Use `.defer("content", ...)` on list views.

- [ ] **I10** | `apps/documents/views/DocumentAuthoring/TemplateSections.py:37` & form choice querysets — Unconstrained full table scans for dropdown querysets loading unused text fields.
  - *Fix*: Use `.only("id", "name", "number")`.

- [ ] **I11** | `apps/documents/views/_common.py:26` — Fragile custom queryset tenant filtering in `documents_object`.
  - *Fix*: Ensure `base.filter(tenant=request.tenant)` is always enforced even if custom queryset is passed.

- [ ] **I12** | `apps/documents/admin.py:1` — `DraftCollaboration` model is omitted from admin model registrations, leaving it without administrative visibility.
  - *Fix*: Import and register `DraftCollaboration` in `apps/documents/admin.py`.

---

## Minor Findings (M1 – M7)

- [ ] **M1** | `apps/documents/views/DocumentAuthoring/DocumentTemplates.py:10` — Unused import `from apps.core.decorators import tenant_admin_required`.
  - *Fix*: Remove unused import.

- [ ] **M2** | `apps/documents/views/DocumentAuthoring/DocumentTemplates.py:151` — `template_instantiate` sets `content=template.content` but does not populate `draft.word_count`.
  - *Fix*: Set `word_count=count_words(template.content)`.

- [ ] **M3** | `apps/documents/views/DocumentAuthoring/*.py` — Redundant dual `COUNT(*)` query in list pagination.
  - *Fix*: Construct `paginator = Paginator(qs, 15)` first, then use `total_count = paginator.count`.

- [ ] **M4** | `apps/documents/views/DocumentAuthoring/TemplateSections.py:33` & `DraftCollaborations.py:35` — Non-standard page size (20 vs NavERP standard 15).
  - *Fix*: Standardize `Paginator(qs, 15)`.

- [ ] **M5** | `apps/documents/views/DocumentAuthoring/DraftCollaborations.py:142` — `collaboration_delete` redirects unconditionally to `documents:draft_detail`, which disrupts navigation when an admin deletes a record directly from `documents:collaboration_list`.
  - *Fix*: Redirect to `documents:collaboration_list` if requested from list.

- [ ] **M6** | `templates/documents/document_authoring/*/list.html` — Missing `for` / `id` attribute coupling on filter form labels and inputs.
  - *Fix*: Add matching `for` and `id` attributes.

- [ ] **M7** | `apps/documents/models/DocumentAuthoring/DocumentDrafts.py:96-102` & `TemplateSections.py:39-45` — Missing composite index on `(tenant, -updated_at)` on DocumentDraft and `(tenant, template, order)` on TemplateSection.
  - *Fix*: Add indexes in models and generate migration.
