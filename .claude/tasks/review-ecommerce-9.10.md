# Review Findings — Sub-module 9.10: Marketing & Campaign Management (Module 9: eCommerce Management System, `ecommerce`)

**Review Baseline:** `f373366542e10cdb8e6b08f6aa8ce4f758c5ad69` (BASE) to `HEAD`  
**Review Passes Completed (6/6):** `code-reviewer` -> `explorer` -> `frontend-reviewer` -> `performance-reviewer` -> `qa-smoke-tester` -> `security-reviewer`

---

## Critical Severity (C)

- [x] **C1**: `templates/ecommerce/marketing_campaign/campaign/detail.html:173` — `NoReverseMatch`: `ecommerce:product_detail` does not exist. Change to `{% url 'ecommerce:catalogproduct_detail' campaign.target_product.pk %}`. — fixed in 65d4b17b
- [x] **C2**: `templates/ecommerce/marketing_campaign/affiliate/detail.html:137` — `NoReverseMatch`: `ecommerce:customerprofile_detail` does not exist. Change to `{% url 'ecommerce:customeraccountprofile_detail' partner.customer_profile.pk %}`. — fixed in 42750899
- [x] **C3**: `templates/ecommerce/marketing_campaign/conversion/detail.html:126` — `NoReverseMatch`: `ecommerce:customerprofile_detail` does not exist. Change to `{% url 'ecommerce:customeraccountprofile_detail' conversion.referred_customer.pk %}`. — fixed in faf7f899
- [x] **C4**: `apps/ecommerce/views/MarketingCampaign/` (`MarketingCampaigns.py`, `AffiliatePartners.py`, `AffiliateReferralConversions.py`, `SeoMetadataRules.py`) — Inverted arguments on all 17 `write_audit_log` call sites. Standard signature is `write_audit_log(user, obj, action, changes=None, tenant=None)`. Update all calls to pass `(request.user, obj, action, changes=..., tenant=request.tenant)`. — fixed in fc025f64, 2c2d49f7, f49d2683, a6cafe9d
- [x] **C5**: `apps/ecommerce/views/MarketingCampaign/AffiliateReferralConversions.py` & `AffiliatePartners.py` — Affiliate conversion accumulator logic: do not credit `total_commission_earned` upon conversion creation (`pending_review`); credit only upon approval (`affiliatereferralconversion_approve`). On `affiliatereferralconversion_void` and `delete`, deduct from `affiliate.total_commission_earned` and `total_revenue_generated` if previously approved. Wrap in `transaction.atomic()`. — fixed in 7e8bb47d
- [x] **C6**: `apps/ecommerce/views/MarketingCampaign/MarketingDashboards.py:72-80` — N+1 query loop in `social_commerce_feed` caused by calling `p.variants.first()` on prefetched related manager. Consume prefetched list in Python: `variants = list(p.variants.all()); first_variant = variants[0] if variants else None`. — fixed in 417b7b26

---

## Important Severity (I)

- [x] **I1**: `apps/ecommerce/forms/MarketingCampaign/` (`AffiliateReferralConversions.py`, `AffiliatePartners.py`, `MarketingCampaigns.py`) — Form Mass Assignment: Remove `status` and `payout_reference` from `Meta.fields` in all three forms so lifecycle transitions are governed exclusively by authenticated view actions. — fixed in b137cf9d, 181ac683, 35b2bdeb
- [x] **I2**: `templates/ecommerce/marketing_campaign/campaign/list.html:121` — Replace undefined CSS badge class `badge-purple` with valid design system class `badge-info`. — fixed in b81c9f60
- [x] **I3**: `apps/core/navigation.py:2735-2738` — Add sub-module query parameters to `LIVE_LINKS["9.10"]` as specified in todo.md: `?channel=email`, `?channel=sms`, `?tab=social`. — fixed in c08be69e
- [x] **I4**: `templates/ecommerce/marketing_campaign/{campaign,affiliate,conversion,seo_rule}/detail.html` — Add standard POST-Delete action form with `csrf_token` and `confirm()` in detail actions headers. — fixed in b46e7e8a, 70ae7bdd, 05b263b1, 06c56be3
- [x] **I5**: `apps/ecommerce/forms/MarketingCampaign/AffiliateReferralConversions.py:54-59` & `AffiliatePartners.py:62-64` — Chained N+1 queries during dropdown rendering: add `.select_related("customer")` on `EcommerceOrder` and `CustomerAccountProfile` form querysets. — fixed in f72716cf, 7648a81c
- [x] **I6**: `apps/ecommerce/views/MarketingCampaign/MarketingCampaigns.py`, `AffiliatePartners.py`, `AffiliateReferralConversions.py` — Lifecycle action concurrency and state guards: wrap `marketingcampaign_send`, `affiliatepartner_approve`, `affiliatereferralconversion_approve`, and `affiliatereferralconversion_void` in `transaction.atomic()` with `select_for_update()` and validate current state. — fixed in 3e98abf8, 6aee869b, 62a92a44
- [x] **I7**: `apps/ecommerce/models/MarketingCampaign/` (`AffiliateReferralConversions.py`, `AffiliatePartners.py`, `SeoMetadataRules.py`) & forms — Non-negative and range validation: add `MinValueValidator(Decimal("0.00"))` on monetary and rate fields, and `MinValueValidator(Decimal("0.00"))` + `MaxValueValidator(Decimal("1.00"))` on `sitemap_priority`. Add clean validation in forms. — fixed in bb1d4116, 670d6ca9, 87e81468, 5f0e483a, 904080be, 3ceb3c3c, c25a50b0
- [x] **I8**: `apps/ecommerce/admin.py:435-469` — Add `readonly_fields` for automated telemetry and aggregate counters across all four 9.10 ModelAdmin classes. — fixed in bf826945, 8344c1f1
- [x] **I9**: `apps/ecommerce/views/MarketingCampaign/` (`MarketingCampaigns.py:44`, `AffiliatePartners.py:40`, `AffiliateReferralConversions.py:40`, `SeoMetadataRules.py:45`) — Change non-standard `Paginator(qs, 25)` to project standard `Paginator(qs, 15)`. — fixed in 88e53224, 773264e5, 8a7e7fca, 891d7fe9
- [x] **I10**: `apps/ecommerce/models/MarketingCampaign/` (`MarketingCampaigns.py`, `AffiliatePartners.py`, `AffiliateReferralConversions.py`, `SeoMetadataRules.py`) — Add composite `models.Index` on `["tenant", "<fk>"]` across all four models. — fixed in 8a43d7ee, b11eeaf5, 60d97939, ad236bdd, ee8ea356
- [x] **I11**: `apps/ecommerce/views/MarketingCampaign/AffiliatePartners.py:66` & `AffiliateReferralConversions.py:66` — In detail views, use `select_related` on chained `user` relations (`customer_profile__user`, `referred_customer__user`). — fixed in 9e11c193, 93a2cb11

---

## Minor Severity (M)

- [x] **M1**: `templates/ecommerce/marketing_campaign/affiliate/detail.html:138` & `conversion/detail.html:127` — Add fallback for nullable `user` on `CustomerAccountProfile`: `|default:partner.customer_profile.customer.name` / `|default:conversion.referred_customer.customer.name`. — fixed in 191fc267, f7949508
- [x] **M2**: `apps/ecommerce/forms/MarketingCampaign/AffiliatePartners.py:64` & `AffiliateReferralConversions.py:59` — In form `__init__`, change `.order_by("user__username")` to `.order_by("customer__name")` on CustomerAccountProfile queryset. — fixed in 43701b70, 1b5b301a
- [x] **M3**: `templates/ecommerce/marketing_campaign/affiliate/list.html:129`, `affiliate/detail.html:28`, `conversion/list.html:134`, `conversion/detail.html:28` — In `{% else %}` badge branch, use `{{ item.get_status_display }}` instead of hardcoded string. — fixed in 42e1df88, 528e92be, a1b79cd8, b9a0792e
- [x] **M4**: `templates/ecommerce/marketing_campaign/{campaign,affiliate,conversion,seo_rule}/form.html` — Add `for="{{ form.<field>.id_for_label }}"` to form labels for accessibility. — fixed in 58f7a329, 3eab35ea, 552519b5, dd183bee
- [x] **M5**: `apps/ecommerce/views/MarketingCampaign/MarketingDashboards.py:25-34` — Combine count and sums into single `.aggregate()` calls. — fixed in dce0e7b0
- [x] **M6**: `apps/ecommerce/views/MarketingCampaign/MarketingDashboards.py:70-73` — Add `.only(...)` to avoid fetching unused text columns for products in social commerce feed. — fixed in dd50253c
- [x] **M7**: `apps/ecommerce/models/MarketingCampaign/AffiliateReferralConversions.py:108` — Simplify `__str__` to `f"Conversion {self.number or 'draft'}"` to avoid two-hop evaluation. — fixed in 53f0c2b8
- [x] **M8**: `apps/ecommerce/views/MarketingCampaign/MarketingDashboards.py:97` — Guard `request.tenant` access with `request.tenant.pk if request.tenant else None`. — fixed in cb308c8f
