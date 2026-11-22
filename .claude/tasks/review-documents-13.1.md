# Review Findings — Sub-module 13.1: Document Creation & Authoring (Module 13: Document Management System, `documents`)

**Changeset**: `046eecb0bbea97d5200c85f8c7a5b81eae74aa9b...HEAD`
**Target App**: `apps/documents/` (Sub-module 13.1: `DocumentAuthoring`)
**Date**: 2026-11-22

---

## 1. Code Reviewer Findings

### Critical
- [ ] `apps/documents/views/DocumentAuthoring/TemplateSections.py:22` — Search filter uses function-call syntax `Q(title__icontains(q))` instead of keyword argument syntax `Q(title__icontains=q)`, raising `NameError: name 'title__icontains' is not defined` on any non-empty query.
- [ ] `apps/documents/views/DocumentAuthoring/DocumentDrafts.py:25` — Search filter uses function-call syntax `Q(title__icontains(q))` instead of keyword argument syntax, raising `NameError: name 'title__icontains' is not defined` whenever `?q=` is passed.
- [ ] `apps/documents/views/DocumentAuthoring/DraftCollaborations.py:24` — Search filter uses function-call syntax `Q(comment_text__icontains(q))` instead of keyword argument syntax, raising `NameError: name 'comment_text__icontains' is not defined` on any search.
- [ ] `apps/documents/views/DocumentAuthoring/DocumentDrafts.py:240` — `draft_promote` instantiates `core.Document` with keyword arguments `title` and `description` which do not exist on `apps.core.models.Document` (which defines `name`), raising `TypeError: Document() got unexpected keyword argument(s) 'title', 'description'` on promotion.

### Important
- [ ] `templates/documents/document_authoring/document_template/detail.html:139` — Traversing nullable `template.owner` in `{{ template.owner.get_full_name|default:template.owner.username|default:"Unassigned" }}` raises `VariableDoesNotExist` and 500s when owner is None (Lesson L10).
- [ ] `apps/documents/views/DocumentAuthoring/DocumentDrafts.py:236` — `draft_promote` lacks a guard checking `if draft.status == "promoted"`, allowing already promoted drafts to be re-promoted repeatedly and generating duplicate released document records.
- [ ] `apps/documents/views/DocumentAuthoring/DraftCollaborations.py:147` — `collaboration_resolve` does not verify `collaboration.status == "open"`, allowing accepted suggestions with `selected_text` matching recurring patterns to be re-applied repeatedly into `draft.content`.
- [ ] `apps/documents/views/DocumentAuthoring/DocumentDrafts.py:173` — `draft_autosave` and `collaboration_create` do not check `draft.is_collaboration_locked`, leaving the review lock inert against concurrent autosaves and suggestions.
- [ ] `apps/documents/admin.py:1` — `DraftCollaboration` model is omitted from admin model registrations, leaving it without administrative visibility.

### Minor
- [ ] `apps/documents/views/DocumentAuthoring/DocumentTemplates.py:10` — Unused import `from apps.core.decorators import tenant_admin_required`.
- [ ] `apps/documents/views/DocumentAuthoring/DocumentTemplates.py:151` — `template_instantiate` sets `content=template.content` but does not populate `draft.word_count`, leaving it at 0 until an edit or autosave occurs.
- [ ] `apps/documents/views/DocumentAuthoring/TemplateSections.py:124` — `template_section_delete` does not warn or prevent deletion of sections flagged as `is_locked=True`.

## 2. Explorer Reviewer Findings

### Critical
- [ ] `apps/documents/views/DocumentAuthoring/TemplateSections.py:22` — Search filter uses function call syntax `Q(title__icontains(q))` instead of keyword argument syntax `Q(title__icontains=q)`. Raises `NameError: name 'title__icontains' is not defined` whenever search query `?q=` is supplied.
- [ ] `apps/documents/views/DocumentAuthoring/DocumentDrafts.py:25` — Search filter uses function call syntax `Q(title__icontains(q))` instead of keyword argument syntax `Q(title__icontains=q)`. Raises `NameError: name 'title__icontains' is not defined` whenever search query `?q=` is supplied.
- [ ] `apps/documents/views/DocumentAuthoring/DraftCollaborations.py:24` — Search filter uses function call syntax `Q(comment_text__icontains(q))` instead of keyword argument syntax `Q(comment_text__icontains=q)`. Raises `NameError: name 'comment_text__icontains' is not defined` whenever search query `?q=` is supplied.
- [ ] `apps/documents/views/DocumentAuthoring/DocumentDrafts.py:240` — `draft_promote` instantiates `core.Document` with keyword arguments `title=draft.title` and `description=...`. `apps.core.models.Document` defines `name` (not `title`) and does not possess a `description` field, raising `TypeError: Document() got unexpected keyword argument(s) 'title', 'description'` on document promotion.

### Important
- [ ] `apps/documents/forms/DocumentAuthoring/DocumentTemplates.py:64-65` — `DocumentTemplateForm.__init__` scopes `target_org_unit` to `self.tenant`, but omits filtering `self.fields["owner"].queryset`. Violates contract Section 2.1 ("Scopes target_org_unit and owner to request.tenant"), leaking cross-tenant users into the form dropdown.
- [ ] `templates/documents/document_authoring/document_template/detail.html:139` — Traversing nullable `template.owner` in `{{ template.owner.get_full_name|default:template.owner.username|default:"Unassigned" }}` without an `{% if template.owner %}` guard violates Lesson L10 and risks `VariableDoesNotExist` under strict evaluation.
- [ ] `apps/documents/admin.py:1` — `DraftCollaboration` model is omitted from `admin.site.register` / `@admin.register`, leaving collaboration comments and track changes without Django admin visibility.
- [ ] `apps/documents/views/DocumentAuthoring/DocumentDrafts.py:236` — `draft_promote` lacks an idempotency check (`if draft.status == "promoted"`), allowing multiple submissions to generate duplicate released `core.Document` records for the same draft.
- [ ] `apps/documents/views/DocumentAuthoring/DraftCollaborations.py:147` — `collaboration_resolve` does not verify `collaboration.status == "open"` prior to applying text replacements, allowing duplicate submissions to replace subsequent matching text in `draft.content`.
- [ ] `apps/documents/views/DocumentAuthoring/DocumentDrafts.py:173` & `DraftCollaborations.py:71` — `draft_autosave` and `collaboration_create` do not check `draft.is_collaboration_locked`, allowing concurrent edits and notes to bypass the collaboration lock.

### Minor
- [ ] `apps/documents/views/DocumentAuthoring/DraftCollaborations.py:142` — `collaboration_delete` redirects unconditionally to `documents:draft_detail`, which disrupts navigation when an admin deletes a record directly from `documents:collaboration_list`.
- [ ] `apps/documents/views/DocumentAuthoring/DocumentTemplates.py:10` — Unused import `from apps.core.decorators import tenant_admin_required`.
- [ ] `apps/documents/views/DocumentAuthoring/DocumentTemplates.py:151` — `template_instantiate` initializes `content=template.content` but leaves `draft.word_count` at 0 until an edit or autosave occurs.
- [ ] `apps/documents/views/DocumentAuthoring/TemplateSections.py:124` — `template_section_delete` permits deletion of sections flagged as `is_locked=True` without validation or warning.

## 3. Frontend Reviewer Findings

### Critical
- [ ] `templates/documents/document_authoring/document_template/detail.html:139` — Lesson L10 `VariableDoesNotExist` 500 crash on nullable user FK filter argument `{{ template.owner.get_full_name|default:template.owner.username|default:"Unassigned" }}`. Fix with `{% if template.owner %}{{ template.owner.get_full_name|default:template.owner.username }}{% else %}Unassigned{% endif %}`. Apply defensive check across sibling user lookups.

### Important
- [ ] `templates/documents/document_authoring/document_draft/canvas.html:43-51` — Undefined `formatDoc()` function in Canvas toolbar causes `ReferenceError`. Implement selection-range text replacement in canvas JS.
- [ ] `templates/documents/document_authoring/draft_collaboration/detail.html:29-53` — Missing POST Delete action and Back-to-List button on Collaboration detail page.
- [ ] `templates/documents/document_authoring/document_draft/canvas.html:80, 127` — Missing `|escapejs` on `insertToken('{{ key|escapejs }}')`, and word count is only updated after server autosave roundtrip instead of live on input.

### Minor
- [ ] `templates/documents/document_authoring/*/list.html` — Missing `for` / `id` attribute coupling on filter form labels and inputs.

## 4. Performance Reviewer Findings

### Critical
- [ ] `apps/documents/views/DocumentAuthoring/DocumentDrafts.py:154-157` & `templates/documents/document_authoring/document_draft/canvas.html:97` — 1 + N N+1 Queries in Canvas View due to Prefetch Cache Invalidation. Calling `.filter(status="open")` invalidates prefetched `collaborations__author` cache. Fix: filter in Python `[c for c in draft.collaborations.all() if c.status == "open"]` or query with `select_related("author")`.
- [ ] `apps/documents/views/DocumentAuthoring/DocumentDrafts.py:66-68` & `templates/documents/document_authoring/document_draft/detail.html:115` — 1 + N N+1 Queries in Draft Detail View due to redundant `.order_by("-created_at")` invalidating prefetched `collaborations` cache. Fix: use `draft.collaborations.all()` directly relying on model Meta ordering.

### Important
- [ ] `apps/documents/views/DocumentAuthoring/DocumentTemplates.py:65-68` — Wasted Prefetch Query and Cache Bypass in `template_detail`: `derived_drafts` prefetch is wasted (only count is rendered), and `.order_by("order", "id")` invalidates `sections` cache. Fix: remove `derived_drafts` from prefetch and use `template.sections.all()`.
- [ ] `apps/documents/views/DocumentAuthoring/TemplateSections.py:99, 125` & `DraftCollaborations.py:136` — Chained lazy FK traversal in audit logging via `__str__` (Lesson L18): `TemplateSection.__str__` accesses `self.template.name` and `DraftCollaboration.__str__` accesses `self.draft.number`. Fix: pass `select_related` to `documents_object` in edit and delete views.
- [ ] `apps/documents/views/DocumentAuthoring/DocumentDrafts.py:21`, `DocumentTemplates.py:19`, `DraftCollaborations.py:20` — Heavy TextFields fetched on list views. Fix: use `.defer("content", ...)` on list views.
- [ ] `apps/documents/views/DocumentAuthoring/TemplateSections.py:37` & form choice querysets — Unconstrained full table scans for dropdown querysets loading unused text fields. Fix: use `.only("id", "name", "number")`.

### Minor
- [ ] `apps/documents/views/DocumentAuthoring/*.py` — Redundant dual `COUNT(*)` query in list pagination. Fix: construct `paginator = Paginator(qs, 15)` first, then use `total_count = paginator.count`.
- [ ] `apps/documents/views/DocumentAuthoring/TemplateSections.py:33` & `DraftCollaborations.py:35` — Non-standard page size (20 vs NavERP standard 15). Fix: standardize `Paginator(qs, 15)`.
- [ ] `apps/documents/models/DocumentAuthoring/DocumentDrafts.py:96-102` & `TemplateSections.py:39-45` — Missing composite index on `(tenant, -updated_at)` on DocumentDraft and `(tenant, template, order)` on TemplateSection.

## 5. QA Smoke Review Findings

### Critical
- [ ] `apps/documents/views/DocumentAuthoring/DocumentDrafts.py:240-244` — TypeError on Document Promotion (`draft_promote`): `core.Document.objects.create(tenant=request.tenant, title=draft.title, description=...)` crashes with `TypeError: Document() got unexpected keyword arguments: 'title', 'description'`. `core.Document` defines `name`, `file`, `classification`, `version`. In addition, `core.Document.file` is non-nullable and requires `ContentFile(draft.content.encode('utf-8'), name=f"{draft.number}.html")` or similar.

### Important
- [ ] `apps/documents/views/DocumentAuthoring/TemplateSections.py:22`, `DocumentDrafts.py:25`, `DraftCollaborations.py:24` — Runtime `NameError` on Search Queries `?q=test`: function call syntax `Q(field__icontains(q))` raises `NameError` on any search. Fix: change to `field__icontains=q`.
- [ ] `templates/documents/document_authoring/document_template/detail.html:139` — Detail page crashes with HTTP 500 when `template.owner = None` due to `django.template.base.VariableDoesNotExist` evaluating `template.owner.username` as filter argument. Fix: guard with `{% if template.owner %}`.
