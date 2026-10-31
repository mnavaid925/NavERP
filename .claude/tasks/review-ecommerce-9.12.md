# Review Findings: Module 9.12 Subscription & Recurring Commerce

Base: `f373366542e10cdb8e6b08f6aa8ce4f758c5ad69`
Head: `eb8ee89239d6ed9f38850b3412fae3cd7cab6293`

---

## 1. Code Reviewer Findings

### Critical
- [ ] `apps/ecommerce/forms/SubscriptionCommerce/CustomerSubscriptions.py:23` — `CustomerSubscriptionForm` includes `started_at` in `Meta.fields` (required since `CustomerSubscription.started_at` lacks `blank=True`), but `started_at` is omitted from `templates/ecommerce/subscriptioncommerce/customersubscription/form.html`. Any form submission from browser fails validation silently.
  - **Fix**: Exclude `started_at` from `CustomerSubscriptionForm.Meta.fields` (using model default `timezone.now` on create and preserving on update) or set `required=False`.

### Important
- [ ] `apps/ecommerce/admin.py:366`, `384` — `CustomerSubscriptionAdmin.search_fields` uses `"customer_profile__customer_name"` and `"customer_profile__email"`, and `SubscriptionRetentionActionAdmin.search_fields` uses `"customer_profile__email"`. `customer_name` and `email` are not fields on `CustomerAccountProfile` directly. Django admin searches crash with `FieldError`.
  - **Fix**: In `CustomerSubscriptionAdmin.search_fields`, use `"customer_profile__customer__name"` and `"customer_profile__user__email"`. In `SubscriptionRetentionActionAdmin.search_fields`, use `"customer_profile__user__email"`.
- [ ] `apps/ecommerce/views/SubscriptionCommerce/CustomerSubscriptions.py:38`, `SubscriptionBoxCurations.py:36` — In `customersubscription_list` and `subscriptionboxcuration_list`, the `plan` GET parameter is queried without `plan_id.isdigit()` validation before passing to `qs.filter(plan_id=plan_id)`. Non-numeric parameters crash with `ValueError` (HTTP 500).
  - **Fix**: Guard with `if plan_id and plan_id.isdigit(): qs = qs.filter(plan_id=int(plan_id))`.
- [ ] `apps/ecommerce/views/SubscriptionCommerce/SubscriptionPortals.py:48`, `:85`, `:140` — Portal mutation actions (`subscription_portal_skip`, `subscription_portal_pause`, and `subscription_portal_deflect`) perform multi-model writes without `transaction.atomic()` and lack status guards preventing operations on already cancelled or expired subscriptions.
  - **Fix**: Wrap mutations in `with transaction.atomic():` and add a status check rejecting actions on cancelled/expired subscriptions.

### Minor
- [ ] `templates/ecommerce/subscriptioncommerce/subscriptionplan/list.html:114` — Plan archetype badge logic explicitly tests `subscribe_save` and `curated_box`, falling through to `badge-slate` for `membership_club`.
  - **Fix**: Explicitly check `elif plan.plan_type == 'membership_club'` and assign `badge-amber` or `badge-info`.

---

## 2. Explorer Findings

### Critical
None.

### Important
- [ ] `apps/ecommerce/views/SubscriptionCommerce/SubscriptionPlans.py:137` — Unhandled `ProtectedError` on subscription plan deletion: In `subscriptionplan_delete`, `plan.delete()` is called without catching `django.db.models.ProtectedError`. Because `CustomerSubscription.plan` is declared with `on_delete=models.PROTECT`, attempting to delete any plan with active or historical subscriptions crashes with HTTP 500. Additionally, the confirmation prompt in `templates/ecommerce/subscriptioncommerce/subscriptionplan/list.html:173` inaccurately claims "Existing subscriptions will remain".
  - **Fix**: Wrap `plan.delete()` in `try...except ProtectedError:` in `subscriptionplan_delete`, notify user with `messages.error(request, f"Cannot delete plan '{name}' because subscriptions are currently assigned to it.")`, redirect safely to `ecommerce:subscriptionplan_detail`, and update the list template confirmation prompt.

### Minor
- [ ] `apps/ecommerce/views/SubscriptionCommerce/SubscriptionBoxCurations.py:48` & `apps/ecommerce/forms/SubscriptionCommerce/SubscriptionBoxCurations.py:73` — Curation plan queryset archetype filtering divergence: Contract Section 4.3 specifies `plans: Queryset of SubscriptionPlan (curated_box type)`. The view and form currently query all active plans regardless of `plan_type` (allowing non-box plans like `subscribe_save` to appear in the curation filter dropdown and form select).
  - **Fix**: Filter `plans` in `subscriptionboxcuration_list` and `SubscriptionBoxCurationForm.__init__` with `.filter(plan_type="curated_box", is_active=True)`.
- [ ] `apps/ecommerce/views/SubscriptionCommerce/SubscriptionPortals.py:19` & `SubscriptionPlans.py:66` — Missing nested `select_related` causing N+1 queries on customer details: `subscription_portal` and `subscriptionplan_detail` query `CustomerSubscription` selecting `customer_profile`, but templates access `sub.customer_profile.customer.name` and `sub.customer_profile.user.email`.
  - **Fix**: Add `"customer_profile__customer"` and `"customer_profile__user"` to `select_related` in `subscription_portal` and `subscriptionplan_detail`.

---

## 3. Frontend Reviewer Findings

### Critical
- [ ] `templates/ecommerce/subscriptioncommerce/customersubscription/form.html` — Missing required form field `started_at` in template causes silent validation failure upon submission.
  - **Fix**: Add `started_at` field input block to `form.html` (or exclude it from form `Meta.fields` as noted by code-reviewer).

### Important
- [ ] `templates/ecommerce/subscriptioncommerce/{subscriptionplan,customersubscription,subscriptionboxcuration,subscriptionretentionaction}/detail.html` — All 4 detail templates omit POST-Delete action forms with CSRF and confirm prompts in their `.page-actions` headers (Rule 4 — CRUD Completeness).
  - **Fix**: Add POST-Delete action forms in the `.page-actions` header of each detail page.

### Minor
- [ ] `templates/ecommerce/subscriptioncommerce/portal/portal.html:133` — Deflection modal close button has no `aria-label` or `title`.
  - **Fix**: Add `aria-label="Close modal"` and `title="Close"`.
- [ ] `templates/ecommerce/subscriptioncommerce/portal/portal.html:140-141` — Deflection reason `<select>` input has no `id` and `<label>` has no `for` attribute.
  - **Fix**: Add `id="cancel-reason-{{ sub.pk }}"` and `for="cancel-reason-{{ sub.pk }}"`.
- [ ] `templates/ecommerce/subscriptioncommerce/portal/portal.html:154, 161, 168` — Radio inputs use non-theme token `text-primary`.
  - **Fix**: Replace `text-primary` with `text-blue-600`.
- [ ] `templates/ecommerce/subscriptioncommerce/subscriptionplan/detail.html:24` — Plan Archetype badge is statically `badge-info`, differing from archetype-based coloring in `list.html`.
  - **Fix**: Apply archetype conditional badge coloring consistent with `list.html`.
- [ ] `templates/ecommerce/subscriptioncommerce/portal/portal.html:129-186` — Deflection modal is nested directly inside `<td>` cell within an overflow table container.
  - **Fix**: Move modal container definitions outside the table wrap to avoid potential stacking context quirks on mobile.

---

## 4. Performance Reviewer Findings

### Critical
- [ ] `apps/ecommerce/views/SubscriptionCommerce/SubscriptionPortals.py:47-196` — Missing `@transaction.atomic` on mutating portal endpoints (`subscription_portal_skip`, `subscription_portal_pause`, `subscription_portal_deflect`). Multi-model updates risk inconsistent state if retention action creation fails.
  - **Fix**: Wrap all three functions in `@transaction.atomic` (or `with transaction.atomic():`).
- [ ] `apps/ecommerce/views/SubscriptionCommerce/SubscriptionPortals.py:23-33` — Python-side loop for Monthly Recurring Revenue (MRR) calculation and unbounded in-memory evaluation of `active_subscriptions`. Violates Rule 5 (balances/KPIs derived via aggregate, never Python loops).
  - **Fix**: Aggregate MRR via database `aggregate(Sum(Case(When(...))))` and slice display querysets.

### Important
- [ ] `apps/ecommerce/views/SubscriptionCommerce/CustomerSubscriptions.py:18-20` — Missing `customer_profile__user` in `select_related` causes N+1 queries (25 extra queries) when rendering email in `customersubscription_list`.
  - **Fix**: Add `"customer_profile__user"` to `select_related`.
- [ ] `apps/ecommerce/views/SubscriptionCommerce/SubscriptionPortals.py:19-21` — Missing `customer_profile__customer` and `customer_profile__user` in `subs_qs.select_related` causes 3N queries across active and paused tables in `subscription_portal`.
  - **Fix**: Add `"customer_profile__customer"` and `"customer_profile__user"` to `subs_qs.select_related`.
- [ ] `apps/ecommerce/views/SubscriptionCommerce/SubscriptionPlans.py:66` — Missing `customer_profile__customer` in `active_subscriptions.select_related` causes 20 extra queries on `subscriptionplan_detail`.
  - **Fix**: Add `"customer_profile__customer"` to `select_related`.
- [ ] `apps/ecommerce/views/SubscriptionCommerce/SubscriptionPortals.py:23-24` — Active and paused tables in `subscription_portal` evaluate unbounded without slicing or pagination.
  - **Fix**: Slice display querysets to `[:25]`.

### Minor
- [ ] `apps/ecommerce/forms/SubscriptionCommerce/SubscriptionRetentionActions.py:48-50` — Chained N+1 query in `subscription` form dropdown options (`CustomerSubscription.__str__` evaluates `customer_profile.customer` and `product.name`).
  - **Fix**: Add `.select_related("customer_profile__customer", "product")` to form's `subscription` queryset.
- [ ] `apps/ecommerce/admin.py:367`, `385` — Missing chained relations in Django admin `list_select_related` (`CustomerSubscriptionAdmin` and `SubscriptionRetentionActionAdmin`).
  - **Fix**: Update `list_select_related` to include chained relations (`customer_profile__customer`, etc.).
- [ ] `apps/ecommerce/models/SubscriptionCommerce/CustomerSubscriptions.py:130-138` — Missing compound index on `(tenant, plan, status)` in `CustomerSubscription`.
  - **Fix**: Add compound index `idx_esub_ten_plan_stat`.
- [ ] `apps/ecommerce/views/SubscriptionCommerce/SubscriptionPortals.py:25-27` & `portal.html:57` — Calling `.count` on sliced `retention_actions[:10]` caps the stat card at 10 instead of total tenant count.
  - **Fix**: Compute `total_retentions` via un-sliced count in view and pass to context.
- [ ] Detail views omit `select_related` when fetching single objects via `ecommerce_object`.
  - **Fix**: Pass `select_related` to `ecommerce_object` in detail views.

---

## 5. QA Smoke Tester Findings

### Critical
None.

### Important
- [ ] `apps/ecommerce/views/SubscriptionCommerce/CustomerSubscriptions.py:39` — `customersubscription_list` crashes with HTTP 500 when non-numeric `?plan=abc` is passed (`ValueError: Field 'id' expected a number but got 'abc'`).
  - **Fix**: Validate with `if plan_id and plan_id.isdigit(): qs = qs.filter(plan_id=int(plan_id))`.
- [ ] `apps/ecommerce/views/SubscriptionCommerce/SubscriptionBoxCurations.py:37` — `subscriptionboxcuration_list` crashes with HTTP 500 when non-numeric `?plan=abc` is passed (`ValueError: Field 'id' expected a number but got 'abc'`).
  - **Fix**: Validate with `if plan_id and plan_id.isdigit(): qs = qs.filter(plan_id=int(plan_id))`.

### Minor
None.




