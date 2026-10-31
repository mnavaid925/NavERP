# Review Findings: Module 9.12 Subscription & Recurring Commerce

Base: `f373366542e10cdb8e6b08f6aa8ce4f758c5ad69`
Head: `eb8ee89239d6ed9f38850b3412fae3cd7cab6293`

Reviewers executed serially:
1. `code-reviewer`
2. `explorer`
3. `frontend-reviewer`
4. `performance-reviewer`
5. `qa-smoke-tester`
6. `security-reviewer`

---

## Critical Findings

- [x] **[C1]** `apps/ecommerce/forms/SubscriptionCommerce/CustomerSubscriptions.py:23` — `CustomerSubscriptionForm` includes `started_at` in `Meta.fields` (required since `CustomerSubscription.started_at` lacks `blank=True`), but `started_at` is omitted from `templates/ecommerce/subscriptioncommerce/customersubscription/form.html`. Any form submission from browser fails validation silently.
  - **Status**: [x] fixed — `started_at` excluded from form `Meta.fields` and defaults automatically via model `timezone.now`.
- [x] **[C2]** `apps/ecommerce/views/SubscriptionCommerce/SubscriptionPortals.py:47-196` — Missing `@transaction.atomic` on mutating portal endpoints (`subscription_portal_skip`, `subscription_portal_pause`, `subscription_portal_deflect`). Multi-model writes risk inconsistent state if retention action creation fails.
  - **Status**: [x] fixed — Added `@transaction.atomic` across all portal mutation endpoints.
- [x] **[C3]** `apps/ecommerce/views/SubscriptionCommerce/SubscriptionPortals.py:23-33` — Python-side loop for Monthly Recurring Revenue (MRR) calculation and unbounded in-memory evaluation of `active_subscriptions`. Violates Rule 5 (derived balances/KPIs via DB aggregate, never Python loops).
  - **Status**: [x] fixed — Replaced with database aggregate query `Sum(cycle_net * mrr_multiplier)` with Coalesce.

---

## Important Findings

- [x] **[I1]** `apps/ecommerce/admin.py:366`, `384` — `CustomerSubscriptionAdmin.search_fields` uses `"customer_profile__customer_name"` and `"customer_profile__email"`, and `SubscriptionRetentionActionAdmin.search_fields` uses `"customer_profile__email"`. Neither `customer_name` nor `email` are fields on `CustomerAccountProfile` directly. Django admin searches crash with `FieldError`.
  - **Status**: [x] fixed — Updated search_fields to span across `customer__name` and `user__email`.
- [x] **[I2]** `apps/ecommerce/views/SubscriptionCommerce/CustomerSubscriptions.py:38` & `SubscriptionBoxCurations.py:36` — In `customersubscription_list` and `subscriptionboxcuration_list`, the `plan` GET parameter is queried without `plan_id.isdigit()` validation before passing to `qs.filter(plan_id=plan_id)`. Non-numeric parameters crash with `ValueError` (HTTP 500).
  - **Status**: [x] fixed — Guarded with `if plan_id and plan_id.isdigit(): qs = qs.filter(plan_id=int(plan_id))`.
- [x] **[I3]** `apps/ecommerce/views/SubscriptionCommerce/SubscriptionPlans.py:137` — Unhandled `ProtectedError` on subscription plan deletion: In `subscriptionplan_delete`, `plan.delete()` is called without catching `django.db.models.ProtectedError`. Because `CustomerSubscription.plan` is declared with `on_delete=models.PROTECT`, attempting to delete any plan with active or historical subscriptions crashes with HTTP 500. Additionally, the confirmation prompt in `templates/ecommerce/subscriptioncommerce/subscriptionplan/list.html:173` inaccurately claims "Existing subscriptions will remain".
  - **Status**: [x] fixed — Wrapped `plan.delete()` in `try...except ProtectedError`, added warning flash message, and updated template confirmation prompt.
- [x] **[I4]** `templates/ecommerce/subscriptioncommerce/{subscriptionplan,customersubscription,subscriptionboxcuration,subscriptionretentionaction}/detail.html` — All 4 detail templates omit POST-Delete action forms with CSRF and confirm prompts in their `.page-actions` headers (Rule 4 — CRUD Completeness).
  - **Status**: [x] fixed — Added standard POST-Delete action forms in `.page-actions` across all 4 detail templates.
- [x] **[I5]** `apps/ecommerce/views/SubscriptionCommerce/CustomerSubscriptions.py:18-20`, `SubscriptionPortals.py:19-21`, `SubscriptionPlans.py:66` — Missing chained relations in `select_related` causes N+1 query storms (`customer_profile__user` in `customersubscription_list`, `customer_profile__customer` and `customer_profile__user` in `subscription_portal`, `customer_profile__customer` in `subscriptionplan_detail`).
  - **Status**: [x] fixed — Added chained FK relations to `select_related` in `CustomerSubscriptions.py`, `SubscriptionPortals.py`, and `SubscriptionPlans.py`.
- [x] **[I6]** `apps/ecommerce/views/SubscriptionCommerce/SubscriptionPortals.py:23-24` — Active and paused tables in `subscription_portal` evaluate unbounded without slicing or pagination.
  - **Status**: [x] fixed — Sliced display querysets to `[:25]`.
- [x] **[I7]** `apps/ecommerce/views/SubscriptionCommerce/SubscriptionPortals.py:46,83,118,138` — Missing `@tenant_admin_required` on mutating actions (`skip`, `pause`, `resume`, `deflect`). Any logged-in non-admin user can modify schedules, cancel contracts, or apply recurring discounts.
  - **Status**: [x] fixed — Applied `@tenant_admin_required` across all mutating actions in `SubscriptionPortals.py`.
- [x] **[I8]** `apps/ecommerce/views/SubscriptionCommerce/SubscriptionPortals.py:48,85,120,140` — Lack of prerequisite lifecycle state guards allows modifying or reviving cancelled/expired subscriptions.
  - **Status**: [x] fixed — Added explicit prerequisite status checks (`status == "active"` or `status == "paused"`).
- [x] **[I9]** `apps/ecommerce/views/SubscriptionCommerce/SubscriptionPortals.py:141-168` — Unvalidated `reason` (causes MariaDB `DataError` if > 50 chars) and unsafe default fallthrough on `action_choice`.
  - **Status**: [x] fixed — Whitelisted `action_choice` and validated `reason` against `SubscriptionRetentionAction.REASON_CHOICES`.
- [x] **[I10]** `apps/ecommerce/models/SubscriptionCommerce/CustomerSubscriptions.py:148` & `apps/ecommerce/forms/SubscriptionCommerce/CustomerSubscriptions.py:85` — Cross-record integrity: `variant` is not validated to belong to the selected `product`.
  - **Status**: [x] fixed — Enforced product variant ownership validation in both model and form `clean()`.

---

## Minor Findings

- [x] **[M1]** `templates/ecommerce/subscriptioncommerce/subscriptionplan/list.html:114` & `detail.html:24` — Archetype badge coloring handles `subscribe_save` and `curated_box`, falling through to `badge-slate` for `membership_club` or rendering statically.
  - **Status**: [x] fixed — Added explicit archetype check for `membership_club` using `badge-amber`.
- [x] **[M2]** `apps/ecommerce/views/SubscriptionCommerce/SubscriptionBoxCurations.py:48` & `apps/ecommerce/forms/SubscriptionCommerce/SubscriptionBoxCurations.py:73` — Curation plan queryset archetype filtering divergence: Contract Section 4.3 specifies `plans: Queryset of SubscriptionPlan (curated_box type)`. The view and form currently query all active plans regardless of `plan_type`.
  - **Status**: [x] fixed — Filtered plan querysets in view and form with `plan_type="curated_box"`.
- [x] **[M3]** `templates/ecommerce/subscriptioncommerce/portal/portal.html:133, 140-141, 154` — Deflection modal accessibility issues (missing `aria-label`/`title` on close button, missing `id`/`for` label association, non-theme `text-primary` class on radio inputs).
  - **Status**: [x] fixed — Added `aria-label`, explicit `id`/`for` bindings, and replaced `text-primary` with `text-blue-600`.
- [x] **[M4]** `templates/ecommerce/subscriptioncommerce/portal/portal.html:129-186` — Deflection modal is nested directly inside `<td>` cell within an overflow table container.
  - **Status**: [x] fixed — Moved modal container definitions outside `.table-wrap`.
- [x] **[M5]** `apps/ecommerce/forms/SubscriptionCommerce/SubscriptionRetentionActions.py:48-50` — Chained N+1 query in `subscription` form dropdown options (`CustomerSubscription.__str__` evaluates `customer_profile.customer` and `product.name`).
  - **Status**: [x] fixed — Added `.select_related("customer_profile__customer", "product")` to form's subscription queryset.
- [x] **[M6]** `apps/ecommerce/admin.py:367`, `385` — Missing chained relations in Django admin `list_select_related` (`CustomerSubscriptionAdmin` and `SubscriptionRetentionActionAdmin`).
  - **Status**: [x] fixed — Added chained relations to `list_select_related`.
- [x] **[M7]** `apps/ecommerce/models/SubscriptionCommerce/CustomerSubscriptions.py:130-138` — Missing compound index on `(tenant, plan, status)` in `CustomerSubscription`.
  - **Status**: [x] fixed — Added `models.Index(fields=["tenant", "plan", "status"], name="idx_esub_ten_plan_stat")` to `CustomerSubscription.Meta.indexes`.
- [x] **[M8]** `apps/ecommerce/views/SubscriptionCommerce/SubscriptionPortals.py:25-27` & `portal.html:57` — Calling `.count` on sliced `retention_actions[:10]` caps the stat card at 10 instead of total tenant count.
  - **Status**: [x] fixed — Computed `total_retentions` via un-sliced count in view and passed to template.
- [x] **[M9]** Detail views omit `select_related` when fetching single objects via `ecommerce_object`.
  - **Status**: [x] fixed — Added relevant `select_related` to `ecommerce_object` across all 4 detail views.
- [x] **[M10]** `apps/ecommerce/models/SubscriptionCommerce/SubscriptionRetentionActions.py:117` — Cross-record integrity: `customer_profile` in retention action is not validated to match `subscription.customer_profile`.
  - **Status**: [x] fixed — Enforced customer profile consistency check against subscription in model and form `clean()`.
