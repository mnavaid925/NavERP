# Test Contract — Projects 7.19 Master Data & Configuration

## Shared setup

- Test subslug: `masterdataconfiguration`
- Shared artifact: `apps/projects/tests/masterdataconfiguration_helpers.py`
- Root fixtures used: `tenant_a`, `tenant_b`, `admin_user`, `member_user`, `admin_b`
- The shared Projects `conftest.py` is concurrently owned by 7.18 and is not edited.
- Every test function starts with `test_masterdataconfiguration_`.
- Every module helper starts with `_masterdataconfiguration_`.
- Factories receive tenant/users explicitly and never seed, flush, or create tenants.
- Dates use `django.utils.timezone`.

## Models

- `ProjectTemplate` [PTM-], `NUMBER_PREFIX=PTM`
- `ProjectCustomField` [PCF-], `NUMBER_PREFIX=PCF`
- `ProjectTeam` [PTE-], `ProjectTeamMember`
- `ProjectLocaleSetting` [PLS-], `NUMBER_PREFIX=PLS`
- WBS JSON is exact-schema, bounded, and rejects invalid downstream choices.
- `ProjectCustomField.save()` synchronizes `core.CustomFieldDefinition` under `module_slug="projects"`.
- Custom values persist only in `core.CustomFieldValue` for stable entity labels.
- Deleting a project definition deactivates its core definition and preserves values.
- Team allocation counts current members only; departed members remain historical.
- Locale defaults are promoted through the single admin-only verb and inherited from core.

## Forms

- `ProjectTemplateForm`
- `ProjectCustomFieldForm`
- `ProjectTeamForm`, `ProjectTeamMemberForm`
- `ProjectLocaleSettingForm`
- `ProjectTemplateInstantiateForm`
- `ProjectCustomFieldFormMixin` integrated into:
  - `ProjectForm`
  - `TaskForm`
  - `MilestoneForm`
  - `ProjectRiskForm`
  - `ProjectTeamForm`
- Custom forms cover text, textarea, integer, decimal, date, boolean, select, multiselect, URL, and user reference.
- Visibility rules can hide a required field without blocking save.
- Tenant-owned querysets are empty without a tenant.

## URLs and authorization

Twenty-six route names are pinned by `.claude/tasks/contract-projects-7.19.md`:

- Templates: `ptm_list`, `ptm_create`, `ptm_detail`, `ptm_edit`, `ptm_delete`, `ptm_instantiate`
- Custom fields: `pcf_list`, `pcf_create`, `pcf_detail`, `pcf_edit`, `pcf_delete`, `pcf_toggle_active`
- Teams: `pte_list`, `pte_create`, `pte_detail`, `pte_edit`, `pte_delete`, `pte_add_member`, `pte_remove_member` (records `left_date` rather than deleting history)
- Locales: `pls_list`, `pls_create`, `pls_detail`, `pls_edit`, `pls_delete`, `pls_set_default`
- Board: `configuration_hub`

Authorization:

- Any authenticated tenant member may read 7.19 pages.
- Any authenticated tenant member may instantiate a project from an active template.
- Tenant configuration mutations are tenant-admin only.
- GET on POST-only configuration verbs returns 405 for members and admins.
- Cross-tenant detail/edit/delete/child targets return 404.
- Tenant-less create requests redirect before form construction.

## Views and context

- All four lists support search, valid filters, deterministic pagination, content-bearing rows, and reset behavior.
- Template list context: `templates`, choices, q, methodology, category, complexity, active state, stats.
- Custom-field list context: `custom_fields`, choices, q, target, type, section, active state, stats.
- Team list context: `teams`, choices/org units, q, type, org unit, active state, stats, paginated current/history members.
- Locale list context: `locale_settings`, global choices, q, active/FK filters, stats.
- Hub context: computed stats, methodology/entity distributions, recent templates/teams.
- Every target detail renders a read-only custom-values panel when definitions exist.

## Migrations

- `0028`: 7.19 base tables
- `0029`: business-calendar help text and newest-first tenant indexes
- `0030`: synchronize project custom-field definitions and remove duplicate task story-point seed
- No core migration is added.

## Four test lanes

1. Models: numbering, validation, WBS bounds, custom-definition synchronization, values, current/history membership, locale inheritance.
2. Forms: all target CRUD payloads, custom field types/visibility/validation, duplicate/race-safe membership, locale working days.
3. Views: all 26 routes, content, filters, pagination, instantiate handoff, member controls, custom-value panels.
4. Security: role gates, method order, CSRF, IDOR, cross-tenant FKs, tenant-less guards, JSON/numeric hostile input, deletion history.
