# Review Findings — Sales 8.14 Partner & Channel Management

Target: Sub-module 8.14 Partner & Channel Management (`apps/sales`)
Base SHA: `d1a87b0f7d6421a166f253bef8ff624c0aeddfa8`
Head SHA: `da85d11a4f51fe395bad9b51ace6dcf994567179`

---

## 1. Code Reviewer Findings

### Verdict
Commit after fixing Important findings (no Critical issues found; multi-tenancy and core spine reuse are robust).

### Critical
None.

### Important
- `templates/sales/partnerchannel/jointaccountplan/detail.html:88` — Unhandled nullable Foreign Key traversal inside template filter argument: `Direct AE: {{ joint_plan.vendor_lead.get_full_name|default:joint_plan.vendor_lead.username|default:"Unassigned" }}` evaluates against nullable `vendor_lead`. Passing an unverified lookup `joint_plan.vendor_lead.username` into the `default` filter risks raising an evaluation exception when `vendor_lead` is `None` (Lesson L10). Fix: wrap in `{% if joint_plan.vendor_lead %}` guard matching line 128 of the same file.
- `apps/sales/views/PartnerChannel/DealRegistrations.py:190` — Missing view-level status guard in `deal_registration_convert`. The view converts any registration with `reg.opportunity is None` without validating that `reg.status == "approved"`, allowing direct POSTs to convert draft, submitted, rejected, or expired registrations. Fix: enforce `if reg.status != "approved": messages.error(request, "Only approved registrations can be converted."); return redirect(...)` in the view.
- `apps/sales/views/PartnerChannel/ChannelConflicts.py:117-122` — Multi-model write in `channel_conflict_create` (`obj.save()` followed by `obj.deal_registration.save(update_fields=[...])`) lacks `transaction.atomic()`. A failure during registration update leaves an orphan dispute row without the linked deal being marked conflicted. Fix: wrap lines 114–122 in `with transaction.atomic():`.
- `templates/sales/partnerchannel/{partnerprofile,dealregistration,jointaccountplan,channelconflict}/detail.html` — Missing POST-only Delete action on all 4 detail pages. The NavERP CRUD specification (Checklist item 6) requires every detail page to provide an Actions block with Back-to-List, Edit, and a POST-only Delete form with CSRF and confirm prompt. Fix: add the standard POST-only delete form to the header/sidebar actions of all 4 detail templates.
- `apps/sales/management/commands/seed_sales.py:3494-3623` — Structural defect in seeder: 8.14 partner and channel management demo data creation is nested inside `_seed_sales_analytics(self, tenant, owner)` instead of residing in its own `_seed_partner_channel(self, tenant, owner)` helper called from `_seed_tenant`. Fix: extract lines 3494–3623 into `def _seed_partner_channel(self, tenant, owner):` and call `self._seed_partner_channel(tenant, owner)` in `_seed_tenant`.

### Minor
- `templates/sales/partnerchannel/partnerprofile/list.html:72-104` — `channel_managers` is queried and passed in the view context, and `channel_manager` is parsed from `request.GET`, but no `<select name="channel_manager">` filter dropdown is rendered in the filter form. Fix: add CAM dropdown to the list filter form.
- `apps/sales/forms/PartnerChannel/DealRegistrations.py:35` & `apps/sales/forms/PartnerChannel/ChannelConflicts.py:33` — `reviewed_at` and `resolved_at` are exposed as editable `datetime-local` inputs in the form `Meta.fields` despite being view-managed timestamps. Fix: exclude system timestamp fields from form `Meta.fields` and let the view set them on adjudication/approval.
- `apps/sales/management/commands/seed_sales.py:154` — The completion message in `seed_sales.py` logs "Sales 8.1, 8.2, 8.3, 8.4, 8.5, 8.6, 8.7, 8.8, 8.9, 8.10, 8.11, and 8.13 seed complete" but omits 8.14. Fix: append 8.14 to the stdout success message.

---

## 2. Explorer Findings

### Verdict
Commit after fixing Important and Minor contract drift items (no Critical issues found; multi-tenancy, Core spine reuse, and package architecture are rock solid).

### Critical
None.

### Important
- URL Route Pattern Drift from Contract (`.../create/` vs `.../new/`): In `.claude/tasks/contract-sales-8.14.md` (Section 3), create route paths are pinned as `partner-channel/partners/new/`, `partner-channel/deal-registrations/new/`, `partner-channel/joint-plans/new/`, `partner-channel/conflicts/new/`. In `apps/sales/urls/PartnerChannel/`, all 4 route patterns were implemented with `/create/`. Fix: update route paths to `.../new/` (or provide aliases).
- Missing `action_items` in `JointAccountPlanForm.Meta.fields`: In `.claude/tasks/contract-sales-8.14.md` (Section 2.3), `JointAccountPlanForm.Meta.fields` specifies `action_items`. In `apps/sales/forms/PartnerChannel/JointAccountPlans.py:16-34`, `action_items` is omitted. Fix: include `action_items` in `Meta.fields` with textarea widget.
- Missing Gap Register File (`.agents/tasks/gaps-sales-8.14.md`): Five deferred features were outlined in `todo.md` (`GAP-sales-8.14-01` to `GAP-sales-8.14-05`), but `.agents/tasks/gaps-sales-8.14.md` has not been authored yet. Fix: author `.agents/tasks/gaps-sales-8.14.md` per project standards.

### Minor
- `templates/sales/partnerchannel/partnerprofile/list.html:72-104` — `channel_managers` is passed in view context but missing `<select name="channel_manager">` in template filter form.
- `templates/sales/partnerchannel/channelconflict/list.html:72-105` — `escalation_level_choices` and `selected_level` are passed in view context but missing `<select name="escalation_level">` in template filter form.
- `apps/sales/urls/PartnerChannel/PartnerProfiles.py:12` & `apps/sales/views/PartnerChannel/PartnerProfiles.py:197` — Console route and view are co-located in `PartnerProfiles.py` rather than separate `PartnerPerformanceConsoles.py` files.

---

## 3. Frontend Reviewer Findings

### Verdict
Needs Fixes — 1 Critical regression risk (Lesson L10 filter-argument 500 on nullable FK), 3 Important findings (missing POST-only Delete actions on all 4 detail views; missing filter dropdowns for channel manager and escalation level), and 3 Minor findings.

### Critical
- `templates/sales/partnerchannel/jointaccountplan/detail.html:88` — Lesson L10 unguarded dotted FK filter argument: evaluating `joint_plan.vendor_lead.username` as an argument to `|default:` when `vendor_lead` is None raises VariableDoesNotExist and causes runtime 500 crash. Fix: wrap with `{% if joint_plan.vendor_lead %}{{ joint_plan.vendor_lead.get_full_name|default:joint_plan.vendor_lead.username }}{% else %}Unassigned{% endif %}`.

### Important
- Missing POST-only Delete action on all 4 detail views (`templates/sales/partnerchannel/{partnerprofile,dealregistration,jointaccountplan,channelconflict}/detail.html`). Fix: add POST delete form in page-actions with CSRF token and confirm dialog.
- Incomplete filter bar in Partner Profile Directory (`templates/sales/partnerchannel/partnerprofile/list.html:72-113`): `channel_manager` dropdown is omitted despite view support and pagination preservation. Fix: add `<select name="channel_manager">`.
- Incomplete filter bar in Channel Conflict Management (`templates/sales/partnerchannel/channelconflict/list.html:72-105`): `escalation_level` dropdown is omitted despite view support and pagination preservation. Fix: add `<select name="escalation_level">`.

### Minor
- `templates/sales/partnerchannel/partnerprofile/form.html:261` — Missing `<label for>` on notes field in Partner Profile form.
- `templates/sales/partnerchannel/jointaccountplan/list.html:154` & `detail.html:22` — Ad-hoc badge pill styling `<span class="text-xs font-medium px-2 py-1 rounded bg-slate-100 text-slate-800">` instead of design system `<span class="badge badge-slate">`.
- All four `list.html` templates — Missing `aria-label` attributes on icon-only table action buttons.


