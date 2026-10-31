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
