# Review Findings — Sub-module 9.10: Marketing & Campaign Management (Module 9: eCommerce Management System, `ecommerce`)

**Review Baseline:** `f373366542e10cdb8e6b08f6aa8ce4f758c5ad69` (BASE) to `HEAD`  
**Review Passes Completed (6/6):** `code-reviewer` -> `explorer` -> `frontend-reviewer` -> `performance-reviewer` -> `qa-smoke-tester` -> `security-reviewer`

---

## Critical Severity (C)

- [ ] **C1**: `templates/ecommerce/marketing_campaign/campaign/detail.html:173` — `NoReverseMatch`: `ecommerce:product_detail` does not exist. Change to `{% url 'ecommerce:catalogproduct_detail' campaign.target_product.pk %}`.
- [ ] **C2**: `templates/ecommerce/marketing_campaign/affiliate/detail.html:137` — `NoReverseMatch`: `ecommerce:customerprofile_detail` does not exist. Change to `{% url 'ecommerce:customeraccountprofile_detail' partner.customer_profile.pk %}`.
- [ ] **C3**: `templates/ecommerce/marketing_campaign/conversion/detail.html:126` — `NoReverseMatch`: `ecommerce:customerprofile_detail` does not exist. Change to `{% url 'ecommerce:customeraccountprofile_detail' conversion.referred_customer.pk %}`.
- [ ] **C4**: `apps/ecommerce/views/MarketingCampaign/` (`MarketingCampaigns.py`, `AffiliatePartners.py`, `AffiliateReferralConversions.py`, `SeoMetadataRules.py`) — Inverted arguments on all 17 `write_audit_log` call sites. Standard signature is `write_audit_log(user, obj, action, changes=None, tenant=None)`. Update all calls to pass `(request.user, obj, action, changes=..., tenant=request.tenant)`.
- [ ] **C5**: `apps/ecommerce/views/MarketingCampaign/AffiliateReferralConversions.py` & `AffiliatePartners.py` — Affiliate conversion accumulator logic: do not credit `total_commission_earned` upon conversion creation (`pending_review`); credit only upon approval (`affiliatereferralconversion_approve`). On `affiliatereferralconversion_void` and `delete`, deduct from `affiliate.total_commission_earned` and `total_revenue_generated` if previously approved. Wrap in `transaction.atomic()`.
- [ ] **C6**: `apps/ecommerce/views/MarketingCampaign/MarketingDashboards.py:72-80` — N+1 query loop in `social_commerce_feed` caused by calling `p.variants.first()` on prefetched related manager. Consume prefetched list in Python: `variants = list(p.variants.all()); first_variant = variants[0] if variants else None`.

---

## Important Severity (I)

- [ ] **I1**: `apps/ecommerce/forms/MarketingCampaign/` (`AffiliateReferralConversions.py`, `AffiliatePartners.py`, `MarketingCampaigns.py`) — Form Mass Assignment: Remove `status` and `payout_reference` from `Meta.fields` in all three forms so lifecycle transitions are governed exclusively by authenticated view actions.
- [ ] **I2**: `templates/ecommerce/marketing_campaign/campaign/list.html:121` — Replace undefined CSS badge class `badge-purple` with valid design system class `badge-info`.
- [ ] **I3**: `apps/core/navigation.py:2735-2738` — Add sub-module query parameters to `LIVE_LINKS["9.10"]` as specified in todo.md: `?channel=email`, `?channel=sms`, `?tab=social`.
- [ ] **I4**: `templates/ecommerce/marketing_campaign/{campaign,affiliate,conversion,seo_rule}/detail.html` — Add standard POST-Delete action form with `csrf_token` and `confirm()` in detail actions headers.
- [ ] **I5**: `apps/ecommerce/forms/MarketingCampaign/AffiliateReferralConversions.py:54-59` & `AffiliatePartners.py:62-64` — Chained N+1 queries during dropdown rendering: add `.select_related("customer")` on `EcommerceOrder` and `CustomerAccountProfile` form querysets.
- [ ] **I6**: `apps/ecommerce/views/MarketingCampaign/MarketingCampaigns.py`, `AffiliatePartners.py`, `AffiliateReferralConversions.py` — Lifecycle action concurrency and state guards: wrap `marketingcampaign_send`, `affiliatepartner_approve`, `affiliatereferralconversion_approve`, and `affiliatereferralconversion_void` in `transaction.atomic()` with `select_for_update()` and validate current state.
- [ ] **I7**: `apps/ecommerce/models/MarketingCampaign/` (`AffiliateReferralConversions.py`, `AffiliatePartners.py`, `SeoMetadataRules.py`) & forms — Non-negative and range validation: add `MinValueValidator(Decimal("0.00"))` on monetary and rate fields, and `MinValueValidator(Decimal("0.00"))` + `MaxValueValidator(Decimal("1.00"))` on `sitemap_priority`. Add clean validation in forms.
- [ ] **I8**: `apps/ecommerce/admin.py:435-469` — Add `readonly_fields` for automated telemetry and aggregate counters across all four 9.10 ModelAdmin classes.
- [ ] **I9**: `apps/ecommerce/views/MarketingCampaign/` (`MarketingCampaigns.py:44`, `AffiliatePartners.py:40`, `AffiliateReferralConversions.py:40`, `SeoMetadataRules.py:45`) — Change non-standard `Paginator(qs, 25)` to project standard `Paginator(qs, 15)`.
- [ ] **I10**: `apps/ecommerce/models/MarketingCampaign/` (`MarketingCampaigns.py`, `AffiliatePartners.py`, `AffiliateReferralConversions.py`, `SeoMetadataRules.py`) — Add composite `models.Index` on `["tenant", "<fk>"]` across all four models.
- [ ] **I11**: `apps/ecommerce/views/MarketingCampaign/AffiliatePartners.py:66` & `AffiliateReferralConversions.py:66` — In detail views, use `select_related` on chained `user` relations (`customer_profile__user`, `referred_customer__user`).

---

## Minor Severity (M)

- [ ] **M1**: `templates/ecommerce/marketing_campaign/affiliate/detail.html:138` & `conversion/detail.html:127` — Add fallback for nullable `user` on `CustomerAccountProfile`: `|default:partner.customer_profile.customer.name` / `|default:conversion.referred_customer.customer.name`.
- [ ] **M2**: `apps/ecommerce/forms/MarketingCampaign/AffiliatePartners.py:64` & `AffiliateReferralConversions.py:59` — In form `__init__`, change `.order_by("user__username")` to `.order_by("customer__name")` on CustomerAccountProfile queryset.
- [ ] **M3**: `templates/ecommerce/marketing_campaign/affiliate/list.html:129`, `affiliate/detail.html:28`, `conversion/list.html:134`, `conversion/detail.html:28` — In `{% else %}` badge branch, use `{{ item.get_status_display }}` instead of hardcoded string.
- [ ] **M4**: `templates/ecommerce/marketing_campaign/{campaign,affiliate,conversion,seo_rule}/form.html` — Add `for="{{ form.<field>.id_for_label }}"` to form labels for accessibility.
- [ ] **M5**: `apps/ecommerce/views/MarketingCampaign/MarketingDashboards.py:25-34` — Combine count and sums into single `.aggregate()` calls.
- [ ] **M6**: `apps/ecommerce/views/MarketingCampaign/MarketingDashboards.py:70-73` — Add `.only(...)` to avoid fetching unused text columns for products in social commerce feed.
- [ ] **M7**: `apps/ecommerce/models/MarketingCampaign/AffiliateReferralConversions.py:108` — Simplify `__str__` to `f"Conversion {self.number or 'draft'}"` to avoid two-hop evaluation.
- [ ] **M8**: `apps/ecommerce/views/MarketingCampaign/MarketingDashboards.py:97` — Guard `request.tenant` access with `request.tenant.pk if request.tenant else None`.
