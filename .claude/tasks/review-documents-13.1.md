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
