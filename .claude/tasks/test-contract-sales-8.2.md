# Test Contract — NavERP 8.2 Opportunity & Pipeline Management

- Phase: 6.1, test contract and shared factories
- App: `apps/sales`
- Namespace: `opportunitypipeline`
- Build contract: `.claude/tasks/contract-sales-8.2.md`
- Test settings: `config.settings_test` with SQLite `:memory:`

## 1. Scope and Ownership

Sub-module 8.2 adds eight Sales models:
1. `OpportunityPipeline`
2. `PipelineStage`
3. `OpportunityPipelinePlacement`
4. `OpportunityTeamMember`
5. `CompetitorProfile`
6. `OpportunityCompetitor`
7. `WinLossReason`
8. `OpportunityOutcome`

It also adds:
- Services & analytics: `opportunity_services.py`, `opportunity_analytics.py`
- Form classes: `OpportunityPipelineForm`, `PipelineStageForm`, `OpportunityPipelinePlacementForm`, `OpportunityTeamMemberForm`, `CompetitorProfileForm`, `OpportunityCompetitorForm`, `WinLossReasonForm`, `OpportunityTransitionForm`
- Views & URLs: Workspace, Board, Visibility, Pipeline configuration & stages, Team members, Competitor profiles, Win/loss reasons, and transitions.

All test functions must follow `test_opportunitypipeline_*` and all helpers `_opportunitypipeline_*`.

## 2. Model Fields & Choices Constants

```python
OPPORTUNITYPIPELINE_MODEL_FIELDS = {
    "OpportunityPipeline": (
        "tenant", "created_at", "updated_at", "number", "name", "code",
        "description", "is_default", "is_active", "currency", "owner",
    ),
    "PipelineStage": (
        "tenant", "created_at", "updated_at", "pipeline", "name", "code",
        "sequence", "stage_kind", "probability", "target_days",
        "require_competitor", "is_active",
    ),
    "OpportunityPipelinePlacement": (
        "tenant", "created_at", "updated_at", "opportunity", "pipeline",
        "current_stage", "stage_entered_at", "probability_override",
    ),
    "OpportunityTeamMember": (
        "tenant", "created_at", "updated_at", "opportunity", "user",
        "role", "notes", "is_active",
    ),
    "CompetitorProfile": (
        "tenant", "created_at", "updated_at", "party", "website",
        "tier", "strengths", "weaknesses", "pricing_model", "notes", "is_active",
    ),
    "OpportunityCompetitor": (
        "tenant", "created_at", "updated_at", "opportunity", "competitor_profile",
        "threat_level", "strategy_notes", "is_primary",
    ),
    "WinLossReason": (
        "tenant", "created_at", "updated_at", "name", "code", "result",
        "category", "requires_competitor", "notes", "is_active",
    ),
    "OpportunityOutcome": (
        "tenant", "created_at", "updated_at", "opportunity", "result",
        "reason", "competitor_link", "closed_at", "recorded_by",
        "decision_maker_feedback", "notes",
    ),
}
```

## 3. URL Names Map

| Entity / Function | URL Name | Kwargs |
|---|---|---|
| Pipeline List | `sales:opportunity_pipeline_list` | None |
| Pipeline Create | `sales:opportunity_pipeline_create` | None |
| Pipeline Detail | `sales:opportunity_pipeline_detail` | `pk` |
| Pipeline Edit | `sales:opportunity_pipeline_edit` | `pk` |
| Pipeline Delete | `sales:opportunity_pipeline_delete` | `pk` |
| Pipeline Set Default | `sales:opportunity_pipeline_set_default` | `pk` |
| Pipeline Stages | `sales:opportunity_pipeline_stages` | `pk` |
| Pipeline Stage Create | `sales:opportunity_pipeline_stage_create` | `pk` |
| Pipeline Stage Edit | `sales:opportunity_pipeline_stage_edit` | `pk`, `stage_pk` |
| Pipeline Stage Delete | `sales:opportunity_pipeline_stage_delete` | `pk`, `stage_pk` |
| Pipeline Stage Reorder | `sales:opportunity_pipeline_stage_reorder` | `pk` |
| Pipeline Board | `sales:opportunity_pipeline_board` | None |
| Pipeline Visibility | `sales:opportunity_pipeline_visibility` | None |
| Opportunity Workspace | `sales:opportunity_workspace_list` | None |
| Opportunity Workspace Detail | `sales:opportunity_workspace_detail` | `pk` |
| Opportunity Place | `sales:opportunity_place` | `pk` |
| Opportunity Unplace | `sales:opportunity_unplace` | `pk` |
| Opportunity Transition | `sales:opportunity_transition` | `pk` |
| Opportunity Team Member Add | `sales:opportunity_team_member_add` | `pk` |
| Opportunity Team Member Edit | `sales:opportunity_team_member_edit` | `pk`, `member_pk` |
| Opportunity Team Member Remove | `sales:opportunity_team_member_remove` | `pk`, `member_pk` |
| Competitor Profile List | `sales:competitor_profile_list` | None |
| Competitor Profile Create | `sales:competitor_profile_create` | None |
| Competitor Profile Detail | `sales:competitor_profile_detail` | `pk` |
| Competitor Profile Edit | `sales:competitor_profile_edit` | `pk` |
| Competitor Profile Delete | `sales:competitor_profile_delete` | `pk` |
| Opportunity Competitor Add | `sales:opportunity_competitor_link_add` | `pk` |
| Opportunity Competitor Edit | `sales:opportunity_competitor_link_edit` | `pk`, `competitor_pk` |
| Opportunity Competitor Remove | `sales:opportunity_competitor_link_remove` | `pk`, `competitor_pk` |
| Win/Loss Reason List | `sales:win_loss_reason_list` | None |
| Win/Loss Reason Create | `sales:win_loss_reason_create` | None |
| Win/Loss Reason Detail | `sales:win_loss_reason_detail` | `pk` |
| Win/Loss Reason Edit | `sales:win_loss_reason_edit` | `pk` |
| Win/Loss Reason Delete | `sales:win_loss_reason_delete` | `pk` |

## 4. Test Files Order

1. `conftest.py` — append helpers & fixtures for 8.2 models
2. `test_opportunitypipeline_models.py` — model invariants, string representations, defaults, choices, auto-numbering, constraints
3. `test_opportunitypipeline_forms.py` — form fields, validation, clean logic, exclusions
4. `test_opportunitypipeline_views.py` — view rendering, querysets, CRUD actions, pagination, analytics, service transitions
5. `test_opportunitypipeline_security.py` — cross-tenant isolation (IDOR -> 404), auth/permission checks, CSRF, input validation
