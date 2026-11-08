# Review Findings — Sub-module 10.18: Collaboration & Data Storytelling (`apps/bi`)

- **Sub-module:** 10.18 Collaboration & Data Storytelling
- **Base SHA:** `769f20c68026ef80014849af810e720d14d817b4`
- **Head SHA:** `f78af891d8c2bb4aeb84f6831f853a007a258e4c`
- **Date:** 2026-11-08

---

## 1. `code-reviewer` Findings

### Critical
1. `apps/bi/forms/CollaborationStorytelling/BiSharedWorkspaces.py:59` — `clean_department` calls `reject_foreign(dept, self.tenant, "Department")`, but `reject_foreign(form, cleaned, names)` expects `(form, cleaned_data, list_of_names)`, raising `AttributeError: 'Tenant' object has no attribute 'get'` and 500-crashing on form submission. Fix: Replace `clean_department` with `def clean(self): cleaned = super().clean(); reject_foreign(self, cleaned, ["department"]); return cleaned`.
2. `apps/bi/forms/CollaborationStorytelling/BiDataStories.py:55` — `clean_workspace` calls `reject_foreign(wspc, self.tenant, "Workspace")` instead of `(self, cleaned, ["workspace"])`, causing `AttributeError: 'Tenant' object has no attribute 'get'` on all story creates/edits. Fix: Replace `clean_workspace` with `def clean(self): cleaned = super().clean(); reject_foreign(self, cleaned, ["workspace"]); return cleaned`.
3. `apps/bi/forms/CollaborationStorytelling/BiVisualComments.py:55, 59, 63, 67` — `clean_dashboard`, `clean_report`, `clean_story`, and `clean_parent_comment` pass `(field_obj, self.tenant, "Name")` to `reject_foreign`, raising `AttributeError: 'Tenant' object has no attribute 'get'` and returning `None` on all visual comment submissions. Fix: Replace the 4 clean methods with `def clean(self): cleaned = super().clean(); reject_foreign(self, cleaned, ["dashboard", "report", "story", "parent_comment"]); return cleaned`.
4. `apps/bi/forms/CollaborationStorytelling/BiDecisionLogs.py:68, 72, 76` — `clean_workspace`, `clean_dashboard`, and `clean_kpi` pass `(field_obj, self.tenant, "Name")` to `reject_foreign`, raising `AttributeError: 'Tenant' object has no attribute 'get'` on decision log form validation. Fix: Replace the 3 clean methods with `def clean(self): cleaned = super().clean(); reject_foreign(self, cleaned, ["workspace", "dashboard", "kpi"]); return cleaned`.

### Important
1. `apps/bi/management/commands/seed_bi.py:104-167` — The `--flush` block in `seed_bi.py` omits `BiDecisionLog`, `BiVisualComment`, `BiDataStory`, and `BiSharedWorkspace`, leaving orphaned records with nullified foreign keys when parent dashboards/KPIs are deleted, and preventing `--flush` from re-seeding 10.18. Fix: Add `BiDecisionLog.objects.all().delete()`, `BiVisualComment.objects.all().delete()`, `BiDataStory.objects.all().delete()`, and `BiSharedWorkspace.objects.all().delete()` to the flush atomic block.
2. `apps/bi/forms/CollaborationStorytelling/BiVisualComments.py:51` — `parent_comment` queryset does not exclude `self.instance.pk` when editing an existing comment, allowing a comment to select itself as its own parent and creating an infinite recursion cycle. Fix: In `__init__`, if `self.instance and self.instance.pk`: `self.fields["parent_comment"].queryset = self.fields["parent_comment"].queryset.exclude(pk=self.instance.pk)`, and validate `parent_comment != self.instance` in `clean()`.
3. `apps/bi/views/CollaborationStorytelling/BiVisualComments.py:80` & `templates/bi/collaboration_storytelling/bivisualcomment/list.html:72-120, 244, 252` — The view context passes `stories` and filters on `?story=`, but the template filter card omits the Story `<select>` dropdown and pagination links do not preserve `&story={{ request.GET.story }}`. Fix: Add the Story filter dropdown to `bivisualcomment/list.html` and include `&story=` in the pagination links.

### Minor
1. `apps/bi/views/CollaborationStorytelling/BiDataStories.py:224` — In `bi_data_story_export_office`, `token = request.GET.get("token", "").strip()` is retrieved from query params but never checked against `story.office_embed_token`. Fix: Validate `if story.office_embed_token and token != story.office_embed_token: return JsonResponse({"error": "Invalid embed token"}, status=403)`.
2. `templates/bi/collaboration_storytelling/bivisualcomment/detail.html:163` — `detail.html` displays the "Resolved By" metadata whenever `comment.resolved_by` is set, even if the comment status was subsequently updated back to `open` or `in_review`. Fix: Guard with `{% if comment.status == 'resolved' and comment.resolved_by %}`.
3. `apps/bi/forms/CollaborationStorytelling/BiVisualComments.py:26-27` — `coordinate_x` and `coordinate_y` are unbounded float inputs in the form despite being percentage coordinates (0–100). Fix: Set `min_value=0`, `max_value=100` on the form fields.

---

## 2. `explorer` Findings

### Critical
*None.*

### Important
1. `apps/bi/views/CollaborationStorytelling/BiDataStories.py:222-225` — `bi_data_story_export_office` extracts `token` query param without validating against `story.office_embed_token`. Detail link sends `?token={{ story.office_embed_token }}`. If the office integration payload is intended to be guarded by this token, an explicit check `if story.office_embed_token and token != story.office_embed_token: return JsonResponse({"error": "Invalid embed token"}, status=403)` should be enforced.

### Minor
1. `apps/bi/views/CollaborationStorytelling/BiVisualComments.py:105-113` — `bi_visual_comment_create` omits `report` and `widget` from `initial` dict when replying to a parent comment (`?parent=<pk>`). When parent comment was attached to a report or widget, `initial["report"]` and `initial["widget"]` are left empty. Fix: Add `initial["report"] = p.report` and `initial["widget"] = p.widget`.
2. `templates/bi/collaboration_storytelling/bidecisionlog/detail.html:95-141` — Template omits rendering of linked `decision.widget` in "Linked Analytical Assets" section, even though widget is present on the model and configurable in the form. Fix: Add grid entry for Linked Widget.
3. Non-rendered JSON fields excluded from forms differ slightly from Pre-build Contract `Meta.fields` (`supporting_documents`, `filter_snapshot`, `mentions_json`, `excel_export_settings`). Handled appropriately via exclusion or custom textareas, but worth documenting.
