# Review Findings — Sales 8.14 Partner & Channel Management

Target: Sub-module 8.14 Partner & Channel Management (`apps/sales`)
Base SHA: `d1a87b0f7d6421a166f253bef8ff624c0aeddfa8`
Head SHA: `da85d11a4f51fe395bad9b51ace6dcf994567179`

Six Reviewers Run:
1. `code-reviewer` — Completed
2. `explorer` — Completed
3. `frontend-reviewer` — Completed
4. `performance-reviewer` — Completed
5. `qa-smoke-tester` — Completed (100% routes 200, IDOR 404, 0 comment leaks)
6. `security-reviewer` — Completed

---

## Consolidated Findings Register

### Critical

- [x] **C1** — `templates/sales/partnerchannel/jointaccountplan/detail.html:88`: Lesson L10 unguarded dotted FK filter argument `{{ joint_plan.vendor_lead.get_full_name|default:joint_plan.vendor_lead.username|default:"Unassigned" }}` causes VariableDoesNotExist and runtime 500 when `vendor_lead` is None.
  - *Fix*: Wrap with `{% if joint_plan.vendor_lead %}{{ joint_plan.vendor_lead.get_full_name|default:joint_plan.vendor_lead.username }}{% else %}Unassigned{% endif %}`.
  - *Status*: [x] fixed — fix(sales): guard dotted vendor_lead attribute access in joint account plan detail

### Important

- [x] **I1** — `apps/sales/views/PartnerChannel/DealRegistrations.py:190`: Missing view-level status guard in `deal_registration_convert`. A direct POST allows converting non-approved deal registrations (draft, submitted, rejected, conflicted) into CRM opportunities.
  - *Fix*: Enforce `if reg.status != "approved": messages.error(request, f"Deal registration {reg.number} cannot be converted because it is not approved."); return redirect(...)` in the view.
  - *Status*: [x] fixed — fix(sales): require approved status before converting deal registration to opportunity

- [x] **I2** — `apps/sales/views/PartnerChannel/ChannelConflicts.py:114-122`: Multi-model write in `channel_conflict_create` (`obj.save()` and `obj.deal_registration.save(update_fields=...)`) lacks `transaction.atomic()`. A failure during registration update leaves an orphan dispute row without the linked deal being marked conflicted.
  - *Fix*: Wrap operations in `with transaction.atomic():`.
  - *Status*: [x] fixed — fix(sales): wrap channel conflict creation and deal registration update in atomic transaction

- [x] **I3** — `templates/sales/partnerchannel/{partnerprofile,dealregistration,jointaccountplan,channelconflict}/detail.html`: Missing POST-only Delete action on all 4 detail templates. Standard NavERP CRUD requires an Actions block with Back-to-List, Edit, and POST-only Delete form with CSRF and confirm prompt.
  - *Fix*: Add POST-only delete form inside `page-actions` across all 4 detail templates, gated by `{% if request.user.is_tenant_admin %}`.
  - *Status*: [x] fixed — feat(sales): add POST-only delete button to partner profile/deal reg/joint plan/conflict detail

- [x] **I4** — `apps/sales/forms/PartnerChannel/DealRegistrations.py:16-39` & `apps/sales/forms/PartnerChannel/ChannelConflicts.py:16-35`: Mass assignment of system timestamps and review/adjudication fields in ModelForms (`reviewed_at`, `reviewed_by` in `DealRegistrationForm`; `resolved_at`, `resolved_by` in `ChannelConflictForm`).
  - *Fix*: Exclude `reviewed_at`, `reviewed_by` from `DealRegistrationForm.Meta.fields`, and `resolved_at`, `resolved_by` from `ChannelConflictForm.Meta.fields`. Manage these fields server-side in views.
  - *Status*: [x] fixed — fix(sales): exclude review/adjudication fields from forms and manage server-side in views

- [x] **I5** — `apps/sales/management/commands/seed_sales.py:3494-3623`: Structural defect in seeder: 8.14 demo data generation logic is nested inside `_seed_sales_analytics` instead of having its own dedicated `_seed_partner_channel(self, tenant, owner)` helper called from `_seed_tenant`.
  - *Fix*: Extract lines 3494–3623 into `def _seed_partner_channel(self, tenant, owner):` and call `self._seed_partner_channel(tenant, owner)` in `_seed_tenant`.
  - *Status*: [x] fixed — refactor(sales): extract _seed_partner_channel helper in seed_sales command

- [x] **I6** — `apps/sales/urls/PartnerChannel/*.py`: Contract route pattern drift: Contract specified `.../new/` while URLconf implemented `.../create/`.
  - *Fix*: Add route patterns for `.../new/` to match contract (while keeping `.../create/` as alias if needed).
  - *Status*: [x] fixed — fix(sales): align PartnerChannel create routes with contract pattern /new/

- [x] **I7** — `apps/sales/forms/PartnerChannel/JointAccountPlans.py:16-34`: Contract drift: `action_items` is in model and contract `Meta.fields`, but omitted from `JointAccountPlanForm.Meta.fields`.
  - *Fix*: Include `action_items` in `Meta.fields` with textarea widget.
  - *Status*: [x] fixed — fix(sales): include action_items in JointAccountPlanForm per contract

- [x] **I8** — `templates/sales/partnerchannel/partnerprofile/list.html:72-113`: Incomplete filter bar: `channel_manager` is parsed in view and preserved in pagination, but `<select name="channel_manager">` is missing from the filter form.
  - *Fix*: Add Channel Account Manager dropdown to the list filter form.
  - *Status*: [x] fixed — feat(sales): add channel manager filter dropdown to partner profile list

- [x] **I9** — `templates/sales/partnerchannel/channelconflict/list.html:72-105`: Incomplete filter bar: `escalation_level` is parsed in view and preserved in pagination, but `<select name="escalation_level">` is missing from the filter form.
  - *Fix*: Add Escalation Tier dropdown to the list filter form.
  - *Status*: [x] fixed — feat(sales): add escalation tier filter dropdown to channel conflict list

- [x] **I10** — `apps/sales/views/PartnerChannel/PartnerProfiles.py:205-230`: Inefficient queries in `partner_performance_console`: 10 queries via per-tier loop and 5 redundant single-metric queries for stat cards.
  - *Fix*: Replace per-tier loop with single grouped `values("tier").annotate(...)`, and collapse separate card queries into two `.aggregate(...)` calls.
  - *Status*: [x] fixed — perf(sales): optimize queries in partner_performance_console using group annotation and aggregation

- [x] **I11** — `.agents/tasks/gaps-sales-8.14.md`: Missing Gap Register File per project standards documenting deferred features (`GAP-sales-8.14-01` through `GAP-sales-8.14-05`).
  - *Fix*: Author `.agents/tasks/gaps-sales-8.14.md` documenting deferred items with owners, blocking conditions, and acceptance criteria.
  - *Status*: [x] fixed — docs(sales): author gaps-sales-8.14.md capturing deferred partner and channel features

### Minor

- [x] **M1** — `apps/sales/views/PartnerChannel/DealRegistrations.py:99`: Unbounded child query on `deal_registration_detail`: `conflicts` queryset lacks slice.
  - *Fix*: Append `[:10]`.
  - *Status*: [x] fixed — perf(sales): bound conflicts query to 10 in deal registration detail view

- [x] **M2** — `templates/sales/partnerchannel/jointaccountplan/list.html:154` & `detail.html:22`: Ad-hoc badge pill styling `<span class="text-xs font-medium px-2 py-1 rounded bg-slate-100 text-slate-800">` instead of design system `<span class="badge badge-slate">`.
  - *Fix*: Replace with `<span class="badge badge-slate">{{ item.get_co_sell_motion_display }}</span>`.
  - *Status*: [x] fixed — style(sales): use design system badge-slate for co-sell motion in joint plan list and detail

- [x] **M3** — `templates/sales/partnerchannel/partnerprofile/form.html:261`: Missing `<label for>` on notes field in Partner Profile form.
  - *Fix*: Add `<label class="form-label" for="{{ form.notes.id_for_label }}">Strategic Notes</label>`.
  - *Status*: [x] fixed — fix(sales): add label for notes field in partner profile form

- [x] **M4** — All four `list.html` templates: Delete buttons in list table actions rendered unconditionally without `{% if request.user.is_tenant_admin %}` check.
  - *Fix*: Wrap in `{% if request.user.is_tenant_admin %}`.
  - *Status*: [x] fixed — feat(sales): gate delete button with is_tenant_admin across all 4 list templates

- [x] **M5** — All four `list.html` templates: Missing `aria-label` attributes on icon-only table action buttons.
  - *Fix*: Add `aria-label` matching `title`.
  - *Status*: [x] fixed — feat(sales): add aria-labels on icon-only table action buttons across all 4 list templates

- [x] **M6** — `apps/sales/management/commands/seed_sales.py:154`: Success output message in `seed_sales.py` omits 8.14.
  - *Fix*: Append 8.14 to stdout log message.
  - *Status*: [x] fixed — fix(sales): include 8.14 in seed_sales success output message

- [x] **M7** — Composite indexes missing on tenant-filtered dropdown columns (`PartnerProfile.partner_type`, `DealRegistration.exclusivity_status`, `JointAccountPlan.co_sell_motion`).
  - *Fix*: Add composite `models.Index` in Meta.indexes.
  - *Status*: [x] fixed — feat(sales): add migration 0026 for PartnerChannel composite indexes
