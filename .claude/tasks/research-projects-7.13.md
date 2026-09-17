# Research — Sub-module 7.13: Agile & Scrum Management (Module 7 — `projects`)

Researched 2026-09-18 against the leading commercial Agile/Scrum and project delivery products: Atlassian Jira (Software, Scrum/Kanban boards, backlog grooming, velocity & burndown), Microsoft Azure Boards / DevOps (Sprints, iterations, capacity planning, retrospective extension), Linear (Cycles, initiatives, triage, burnup/burndown), GitLab Agile Planning (Iterations, milestones, epics, roadmaps), Broadcom Rally / CA Agile Central, and ClickUp Agile.

## The five NavERP.md bullets, mapped

1. **Sprint Planning & Backlog Grooming** — Story point estimation, velocity tracking, and backlog prioritization.
   - Core Container: `Sprint` [SPT-] (status: planning, active, completed, cancelled; timebox start/end dates; committed story points snapshot).
   - In-place task extension: `ProjectTask.story_points` (positive small integer: Fibonacci/standard 0-100) and `ProjectTask.sprint` FK.
   - Backlog grooming workbench: `projects:sprint_backlog` computed page for unassigned tasks (`sprint__isnull=True`), priority ordering (MoSCoW, priority, sequence), and sprint assignment.
   - Velocity tracking: computed historical velocity (committed vs completed story points across past completed sprints).

2. **Sprint Execution & Daily Standups** — Burndown charts, impediment tracking, and standup note capture.
   - `Sprint` execution surface: `projects:sprint_execution` active sprint board with daily standup note capture.
   - Burndown charts: dynamic calculation of ideal burn slope vs actual daily remaining story points.
   - Blocker/impediment tracking: `SprintImpediment` [IMP-] register for team-level impediments (severity, status, owner, resolution notes, `imp_resolve` action).

3. **Release & Version Planning** — Release trains, feature flags, and version roadmap visualization.
   - Core Entity: `ProjectRelease` [REL-] (version tag, planned release date, status: unreleased, in_progress, released, archived; release notes; feature flag toggle notes).
   - Task/story linkage: `ProjectTask.release` FK.
   - Release roadmap visualization: `projects:release_roadmap` timeline displaying active release trains and completion progress.

4. **Epic & Feature Management** — Hierarchical story organization, cross-sprint feature tracking, and progress rollups.
   - Core Entity: `ProjectEpic` [EPC-] (project, name, summary, status: draft, in_progress, completed, cancelled; target window, color code).
   - Task/story linkage: `ProjectTask.epic` FK.
   - Progress rollup: derived properties for `total_points`, `completed_points`, and `progress_percent` calculated dynamically across member tasks (Ruling 1: no stale progress columns).

5. **Retrospectives & Team Health** — Sprint retrospective boards, action item tracking, and team sentiment surveys.
   - Core Entity: `SprintRetrospective` [RET-] (linked to `Sprint`, conducted date, facilitator/scrum master, sentiment score 1.0-5.0 from team sentiment surveys).
   - Retro board sections: `what_went_well`, `what_needs_improvement`, and `action_items` with assignees and due dates.
   - Team health reporting: `projects:velocity_report` visualizes sentiment scores over consecutive sprints alongside velocity.

---

## Recommended scope (5 domain models + in-place task extension + 4 computed pages)

- `Sprint` [SPT-] — the sprint container: project FK, name, goal, status (`planning`, `active`, `completed`, `cancelled`), dates, `committed_points`, `scrum_master`, `standup_notes`, `started_at`, `completed_at`.
- `ProjectEpic` [EPC-] — the cross-sprint feature / epic container: project FK, name, summary, status, owner, target window, color code.
- `ProjectRelease` [REL-] — the release train / version container: project FK, name, `version_tag`, status, `release_date`, `release_notes`, `feature_flags`, `released_at`, `released_by`.
- `SprintImpediment` [IMP-] — the team blocker register: sprint FK, title, description, severity, status (`open`, `in_progress`, `resolved`), owner, `raised_by`, `resolved_at`, `resolution_notes`.
- `SprintRetrospective` [RET-] — the retrospective and health survey: sprint FK, conducted date, conducted by, status (`draft`, `open`, `closed`), `sentiment_score` (1.0–5.0), `what_went_well`, `what_needs_improvement`, `action_items`.
- `ProjectTask` (in-place extension) — adds nullable `story_points`, `sprint`, `epic`, `release`.
- Computed pages (no database tables that go stale):
  - `sprint_backlog` — backlog grooming and sprint planning workbench.
  - `sprint_execution` — active sprint board, burndown chart, and daily standup notes.
  - `velocity_report` — historical velocity chart and team sentiment trend.
  - `release_roadmap` — release train visualization and milestone tracking.

---

## Rulings

1. **No second task or story table (L29 / Ruling 1).**
   Agile user stories and tasks are `ProjectTask` rows. Sprints, Epics, and Releases link to `ProjectTask` directly.
2. **No stored progress or health columns.**
   Epic progress, release progress, and sprint completion rates are derived properties calculated on read from member tasks.
3. **No hard-coded or duplicate financial/risk ledgers.**
   Cost remains in 7.4; cross-project dependencies in 7.12; task dependencies in 7.2.
4. **Verbs drive state machine transitions.**
   Transitions (`spt_start`, `spt_complete`, `rel_publish`, `imp_resolve`, `ret_close`) write through POST-only views and produce audit log rows with action length ≤ 10 chars.
5. **Multi-tenancy and permissions.**
   All queries scoped to `request.tenant`; all views `@login_required`; foreign tenant FKs strictly rejected in forms.
