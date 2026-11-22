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
