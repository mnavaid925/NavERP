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

- [x] **[C1]** `apps/ecommerce/forms/SubscriptionCommerce/CustomerSubscriptions.py:23` — fixed — excluded started_at from CustomerSubscriptionForm fields
- [x] **[C2]** `apps/ecommerce/views/SubscriptionCommerce/SubscriptionPortals.py:47-196` — fixed — wrapped mutating portal endpoints in atomic transactions
- [x] **[C3]** `apps/ecommerce/views/SubscriptionCommerce/SubscriptionPortals.py:23-33` — fixed — aggregated MRR via database aggregate with cadence weighting

---

## Important Findings

- [x] **[I1]** `apps/ecommerce/admin.py:366`, `384` — fixed — corrected admin search_fields to customer_profile__customer__name and customer_profile__user__email
- [x] **[I2]** `apps/ecommerce/views/SubscriptionCommerce/CustomerSubscriptions.py:38` & `SubscriptionBoxCurations.py:36` — fixed — guarded plan GET filter with plan_id.isdigit()
- [x] **[I3]** `apps/ecommerce/views/SubscriptionCommerce/SubscriptionPlans.py:137` — fixed — handled ProtectedError in subscriptionplan_delete and updated confirmation prompt in list template
- [x] **[I4]** `templates/ecommerce/subscriptioncommerce/{subscriptionplan,customersubscription,subscriptionboxcuration,subscriptionretentionaction}/detail.html` — fixed — added POST-Delete forms with CSRF and confirm prompts to all 4 detail page action headers
- [x] **[I5]** `apps/ecommerce/views/SubscriptionCommerce/CustomerSubscriptions.py:18-20`, `SubscriptionPortals.py:19-21`, `SubscriptionPlans.py:66` — fixed — added chained customer_profile relations to select_related across views
- [x] **[I6]** `apps/ecommerce/views/SubscriptionCommerce/SubscriptionPortals.py:23-24` — fixed — sliced active and paused subscription display querysets to [:25]
- [x] **[I7]** `apps/ecommerce/views/SubscriptionCommerce/SubscriptionPortals.py:46,83,118,138` — fixed — added tenant_admin_required to skip, pause, resume, and deflect portal actions
- [x] **[I8]** `apps/ecommerce/views/SubscriptionCommerce/SubscriptionPortals.py:48,85,120,140` — fixed — guarded lifecycle state transitions (active required for skip/pause/deflect; paused required for resume)
- [x] **[I9]** `apps/ecommerce/views/SubscriptionCommerce/SubscriptionPortals.py:141-168` — fixed — validated action_choice against allowed set and clamped reason to REASON_CHOICES
- [x] **[I10]** `apps/ecommerce/models/SubscriptionCommerce/CustomerSubscriptions.py:148` & `apps/ecommerce/forms/SubscriptionCommerce/CustomerSubscriptions.py:85` — fixed — validated that variant belongs to selected product in model and form clean()

---

## Minor Findings

- [x] **[M1]** `templates/ecommerce/subscriptioncommerce/subscriptionplan/list.html:114` & `detail.html:24` — fixed — added badge-amber styling for membership_club archetype across list and detail templates
- [x] **[M2]** `apps/ecommerce/views/SubscriptionCommerce/SubscriptionBoxCurations.py:48` & `apps/ecommerce/forms/SubscriptionCommerce/SubscriptionBoxCurations.py:73` — fixed — filtered plan queryset in view and form to curated_box archetype per contract
- [x] **[M3]** `templates/ecommerce/subscriptioncommerce/portal/portal.html:133, 140-141, 154` — fixed — added aria-label/title on close button, id/for label association, and replaced text-primary with text-blue-600
- [x] **[M4]** `templates/ecommerce/subscriptioncommerce/portal/portal.html:129-186` — fixed — moved deflection modals outside table-wrap to prevent stacking context quirks
- [x] **[M5]** `apps/ecommerce/forms/SubscriptionCommerce/SubscriptionRetentionActions.py:48-50` — fixed — added customer_profile__customer and product to select_related in form subscription queryset
- [ ] **[M6]** `apps/ecommerce/admin.py:367`, `385` — Missing chained relations in Django admin `list_select_related` (`CustomerSubscriptionAdmin` and `SubscriptionRetentionActionAdmin`).
  - **Fix**: Update `list_select_related` to include chained relations (`customer_profile__customer`, etc.).
- [ ] **[M7]** `apps/ecommerce/models/SubscriptionCommerce/CustomerSubscriptions.py:130-138` — Missing compound index on `(tenant, plan, status)` in `CustomerSubscription`.
  - **Fix**: Add compound index `idx_esub_ten_plan_stat` in `Meta.indexes`.
- [ ] **[M8]** `apps/ecommerce/views/SubscriptionCommerce/SubscriptionPortals.py:25-27` & `portal.html:57` — Calling `.count` on sliced `retention_actions[:10]` caps the stat card at 10 instead of total tenant count.
  - **Fix**: Compute `total_retentions` via un-sliced count in view and pass to context.
- [ ] **[M9]** Detail views omit `select_related` when fetching single objects via `ecommerce_object`.
  - **Fix**: Pass `select_related` to `ecommerce_object` in detail views.
- [ ] **[M10]** `apps/ecommerce/models/SubscriptionCommerce/SubscriptionRetentionActions.py:117` — Cross-record integrity: `customer_profile` in retention action is not validated to match `subscription.customer_profile`.
  - **Fix**: In `SubscriptionRetentionAction.clean()`, ensure `self.customer_profile_id == self.subscription.customer_profile_id`.
