# Review wave — procurement 6.6 RFx Management (2026-08-26)

Six parallel read-only lanes over the 6.6 changeset
(`apps/procurement/{models,forms,views,urls}/RfxManagement/`, `migrations/0008_rfx_management.py`,
the `_seed_rfx` seeder block, `templates/procurement/rfxmanagement/**`, RFx admin registrations).
QA lane additionally executed `manage.py check`, double `seed_procurement`,
`temp/smoke_66.py`, `temp/smoke66_post.py` and its own cross-tenant edge probe — all green.

| Lane | Findings |
|---|---|
| code-reviewer | 7 (1 High, 2 Medium, 4 Low) |
| explorer | 6 (1 Medium, 3 Low, 2 Info) |
| frontend-reviewer | 6 (1 Medium, 5 Low) |
| performance-reviewer | 3 (1 Medium accepted-as-noted, 2 Low) |
| qa-smoke-tester | 0 — all green (check/seed×2/smokes/edge probe exit 0) |
| security-reviewer | 4 (2 Important, 2 Minor) |

## Consolidated fix list (apply in this order)

| ID | Sev | Status | File | Problem | Fix |
|---|---|---|---|---|---|
| F-CR-01 | High | [ ] | forms/RfxManagement/Responses.py L36-39 | `clean()` calls `add_error("event",…)` after `__init__` popped `event` on edit → ValueError 500 on every closed-event scoring save; also wrongly forbids post-close evaluation | Enforce accepts_responses only on create (`if self.instance.pk is None and event is not None and not event.accepts_responses`) |
| F-SE-01 | Important | [ ] | forms/RfxManagement/Responses.py (RfxResponseForm) | attachment FileField has no extension/size allowlist; media served same-origin from webroot → stored-XSS/malware surface | Add `clean_attachment` allowlist (.pdf/.doc/.docx/.xls/.xlsx/.png/.jpg/.txt) + size cap (10 MB), mirroring the HRM upload-validation pattern |
| F-SE-02 | Important | [ ] | admin.py RfxResponseAdmin/RfxEventAdmin | admin can flip `status`, edit frozen answers and issued-event questions, bypassing STATUS_FLOW/is_locked/is_editable | `status` into readonly_fields; RfxAnswerInline change-permission False when parent locked; RfxQuestionInline edit gated on event.is_editable |
| F-CR-02 | Medium | [ ] | views/RfxManagement/Responses.py rfx_response_delete | submitted+ responses of an ISSUED event deletable, silently removing bids mid-RFP (docstring says repository keeps them) | Refuse delete whenever `obj.status != "draft"` |
| F-CR-03 / F-EX-02 | Medium | [ ] | views/RfxManagement/Responses.py rfx_response_create | `isdecimal()+int()` GET parse misses the L11 over-range guard → driver OverflowError | Use `apps.core.crud.as_db_int` |
| F-EX-01 | Medium | [ ] | views/RfxManagement/Responses.py L65 | `initial["event"] = <instance>` never preselects (ModelChoiceField wants pk) → ?event= deep-link dead | Set `initial["event"] = pk` (int) after tenant-scoped existence check |
| F-FE-01 / F-EX-04 | Medium | [ ] | views/RfxManagement/Events.py rfx_detail + events/detail.html L24 | Compare button gates on rows including disqualified while compare excludes them → button leads to empty matrix | Count admissible submissions (SUBMITTED_STATUSES) in view; gate button on that |
| F-CR-04 | Low | [ ] | models/RfxManagement/Responses.py transition() | disqualified→under_review reinstate permitted on CANCELLED event → live-looking frozen row | Reject transitions to submitted/under_review when event.status == "cancelled" |
| F-CR-05 | Low | [ ] | views/RfxManagement/Events.py rfx_question_move (+forms _next_order) | reorder/max-order read-modify-write unlocked → concurrent moves can duplicate orders | Wrap in atomic + `select_for_update` on the event's questions (lock parent row for _next_order) |
| F-SE-03 | Minor | [ ] | forms/RfxManagement/Responses.py factory | answer formset lacks max_num/validate_max → crafted TOTAL_FORMS CPU amplification + unattached-row IntegrityError noise | `max_num=60, validate_max=True`; keep the question_id-None graceful skip |
| F-CR-06 | Low | [ ] | forms/RfxManagement/Responses.py BaseRfxAnswerFormSet.clean | off-list-choice check unreachable (ChoiceField already rejects) — comment claims distinct guard | Reword comment as belt-and-braces defence, keep check |
| F-CR-07 | Low | [ ] | seed_procurement.py _seed_rfx plans | docstring promises "one fully scored" but both responses miss Q2 (heaviest weight) | Northwind scores → ["8","7","7"] (fully scored); Cascade stays partial |
| F-EX-03 / F-FE-03 | Low | [ ] | templates/procurement/rfxmanagement/responses/form.html L26 | `questions_note` never supplied; card hidden when description blank | Drop `or questions_note` |
| F-FE-02 | Low | [ ] | templates/procurement/rfxmanagement/events/detail.html L80 | empty-state colspan hardcoded 8 vs conditional 7-col table | Conditional colspan |
| F-FE-04 | Low | [ ] | templates/procurement/rfxmanagement/responses/list.html L57 | Edit pencil unconditional → dead-end for locked/cancelled | Guard like events/detail.html |
| F-FE-05 | Low | [ ] | templates/procurement/rfxmanagement/scoring.html | No Actions column (inconsistent with sibling lists) | Add eye btn-icon → response detail |
| F-FE-06 | Low | [ ] | all rfx templates | icon-only controls rely on title alone | Add aria-label alongside title |
| F-PF-02 / F-PF-03 | Low | [ ] | responses/detail.html footer, events/detail.html L43/L117 | score_percent recomputes both aggregates; possible_points rendered 2-3× per request | Precompute earned/possible/pct once in the view, pass via context |
| F-EX-05 | Info | [ ] | views/RfxManagement/Responses.py rfx_response_detail | dead `status_choices` context var | Remove |
| F-EX-06 | Info | [ ] | seed_procurement.py module docstring | header doesn't mention the 6.6 block | Extend docstring |

## Accepted / not-actionable

| ID | Reason |
|---|---|
| F-PF-01 | Scoring leaderboard materializes tenant-wide submissions before ranking — reviewer judged acceptable at current scale; revisit with DB-side ranking when volumes grow (noted here deliberately) |
| Security residual | is_template allowed on issued-but-response-less event — folded into F-SE-02 scope creep guard? NO: tracked as follow-up note only |

## Verification after fixes
Re-run `temp\smoke_66.py`, `temp\smoke66_post.py`, `manage.py check`, and
`venv\Scripts\python.exe -m pytest apps\procurement\tests -q --no-migrations -k "rfx"` (once the
test wave lands). Known pre-existing failures in `test_awe_*` belong to the concurrent 6.3
session's review commits, NOT this sub-module.
