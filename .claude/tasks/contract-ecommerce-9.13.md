# Contract — Sub-module 9.13: Reviews & User-Generated Content (Module 9: eCommerce Management System, `ecommerce`)

- **Sub-module:** 9.13 Reviews & User-Generated Content · **Module:** 9 eCommerce Management System · **App:** `apps/ecommerce`
- **Date:** 2026-10-31 · **Status:** FROZEN PRE-BUILD CONTRACT · **Phase:** 3.1 Spec
- **App Status:** Extending existing `apps/ecommerce/`. Next incremental migration: `0018_...`
- **Package Layout:** `ReviewUgc/` across `models/`, `forms/`, `views/`, `urls/`, and templates `templates/ecommerce/review_ugc/`.

---

## 1. Models & CHOICES Contract

All top-level models inherit from `apps.ecommerce.models._base.TenantNumbered` (`tenant`, `number`, `created_at`, `updated_at`).

### 1.1 `ProductReview` (`apps/ecommerce/models/ReviewUgc/ProductReviews.py`)
- **Table:** `ecommerce_product_review`
- **Number Prefix:** `EPRV` (`EPRV-00001`)
- **CHOICES:**
  - `RATING_CHOICES = [(1, '1 Star - Poor'), (2, '2 Stars - Fair'), (3, '3 Stars - Good'), (4, '4 Stars - Very Good'), (5, '5 Stars - Excellent')]`
  - `STATUS_CHOICES = [('pending', 'Pending Moderation'), ('approved', 'Approved'), ('rejected', 'Rejected'), ('flagged_spam', 'Flagged as Spam')]`
  - `SENTIMENT_CHOICES = [('positive', 'Positive'), ('neutral', 'Neutral'), ('negative', 'Negative'), ('mixed', 'Mixed')]`
- **Fields:**
  - `tenant`: `ForeignKey('core.Tenant', on_delete=CASCADE, related_name='+')`
  - `number`: `CharField(max_length=20, editable=False)`
  - `product`: `ForeignKey('ecommerce.CatalogProduct', on_delete=CASCADE, related_name='customer_reviews')`
  - `variant`: `ForeignKey('ecommerce.ProductVariant', on_delete=SET_NULL, null=True, blank=True, related_name='customer_reviews')`
  - `customer`: `ForeignKey('ecommerce.CustomerAccountProfile', on_delete=SET_NULL, null=True, blank=True, related_name='reviews')`
  - `order`: `ForeignKey('ecommerce.EcommerceOrder', on_delete=SET_NULL, null=True, blank=True, related_name='reviews')`
  - `reviewer_name`: `CharField(max_length=120, help_text="Public display name")`
  - `reviewer_email`: `EmailField(help_text="Private email for verification")`
  - `rating`: `PositiveSmallIntegerField(choices=RATING_CHOICES, default=5)`
  - `title`: `CharField(max_length=200, help_text="Review headline")`
  - `body`: `TextField(help_text="Detailed customer review text")`
  - `status`: `CharField(max_length=25, choices=STATUS_CHOICES, default='pending')`
  - `sentiment`: `CharField(max_length=20, choices=SENTIMENT_CHOICES, default='neutral')`
  - `sentiment_score`: `DecimalField(max_digits=5, decimal_places=2, default=Decimal('0.00'), help_text="Score from -1.00 (negative) to +1.00 (positive)")`
  - `is_verified_purchase`: `BooleanField(default=False)`
  - `is_featured`: `BooleanField(default=False, help_text="Pin to top of review list")`
  - `media_urls`: `JSONField(default=list, blank=True, help_text="List of attached photo/video URLs")`
  - `helpful_votes`: `PositiveIntegerField(default=0)`
  - `unhelpful_votes`: `PositiveIntegerField(default=0)`
  - `merchant_response`: `TextField(blank=True, help_text="Official merchant public reply")`
  - `merchant_response_at`: `DateTimeField(null=True, blank=True)`
  - `moderated_by`: `ForeignKey('accounts.User', on_delete=SET_NULL, null=True, blank=True, related_name='moderated_reviews')`
  - `moderation_note`: `CharField(max_length=255, blank=True)`
  - `created_at`: `DateTimeField(auto_now_add=True)`
  - `updated_at`: `DateTimeField(auto_now=True)`
- **Constraints & Indexes:**
  - `UniqueConstraint(fields=['tenant', 'number'], name='ecommerce_eprv_tenant_num_uniq')`
  - `Index(fields=['tenant', 'product', 'status'], name='idx_eprv_ten_prod_stat')`
  - `Index(fields=['tenant', 'rating', 'status'], name='idx_eprv_ten_rate_stat')`
  - `Index(fields=['tenant', 'sentiment'], name='idx_eprv_ten_snt')`

---

### 1.2 `ProductQuestionAnswer` (`apps/ecommerce/models/ReviewUgc/ProductQuestionAnswers.py`)
- **Table:** `ecommerce_product_question_answer`
- **Number Prefix:** `EPQA` (`EPQA-00001`)
- **CHOICES:**
  - `STATUS_CHOICES = [('pending', 'Pending Moderation'), ('approved', 'Approved'), ('rejected', 'Rejected')]`
- **Fields:**
  - `tenant`: `ForeignKey('core.Tenant', on_delete=CASCADE, related_name='+')`
  - `number`: `CharField(max_length=20, editable=False)`
  - `product`: `ForeignKey('ecommerce.CatalogProduct', on_delete=CASCADE, related_name='questions_and_answers')`
  - `author_name`: `CharField(max_length=120, help_text="Public author name")`
  - `author_email`: `EmailField(blank=True, help_text="Private email for notifications")`
  - `customer`: `ForeignKey('ecommerce.CustomerAccountProfile', on_delete=SET_NULL, null=True, blank=True, related_name='questions')`
  - `question_text`: `TextField(help_text="Customer pre-purchase inquiry")`
  - `status`: `CharField(max_length=20, choices=STATUS_CHOICES, default='pending')`
  - `answer_text`: `TextField(blank=True, help_text="Staff or expert response")`
  - `answered_by_name`: `CharField(max_length=120, blank=True)`
  - `is_staff_answer`: `BooleanField(default=False)`
  - `answered_by_user`: `ForeignKey('accounts.User', on_delete=SET_NULL, null=True, blank=True, related_name='product_answers')`
  - `answered_at`: `DateTimeField(null=True, blank=True)`
  - `helpful_votes`: `PositiveIntegerField(default=0)`
  - `is_pinned`: `BooleanField(default=False, help_text="Pin to top of Q&A section")`
  - `created_at`: `DateTimeField(auto_now_add=True)`
  - `updated_at`: `DateTimeField(auto_now=True)`
- **Constraints & Indexes:**
  - `UniqueConstraint(fields=['tenant', 'number'], name='ecommerce_epqa_tenant_num_uniq')`
  - `Index(fields=['tenant', 'product', 'status'], name='idx_epqa_ten_prod_stat')`
  - `Index(fields=['tenant', 'is_pinned'], name='idx_epqa_ten_pinned')`

---

### 1.3 `VisualUgcMedia` (`apps/ecommerce/models/ReviewUgc/VisualUgcMedia.py`)
- **Table:** `ecommerce_visual_ugc_media`
- **Number Prefix:** `EUGC` (`EUGC-00001`)
- **CHOICES:**
  - `MEDIA_TYPE_CHOICES = [('photo', 'Customer Photo'), ('video', 'Customer Video'), ('instagram', 'Instagram Post'), ('tiktok', 'TikTok Video')]`
  - `RIGHTS_STATUS_CHOICES = [('approved', 'Rights Approved / Uploaded'), ('pending_request', 'Rights Requested'), ('rejected', 'Rejected / No Rights')]`
- **Fields:**
  - `tenant`: `ForeignKey('core.Tenant', on_delete=CASCADE, related_name='+')`
  - `number`: `CharField(max_length=20, editable=False)`
  - `media_type`: `CharField(max_length=20, choices=MEDIA_TYPE_CHOICES, default='photo')`
  - `media_url`: `URLField(max_length=500, help_text="Direct media URL")`
  - `thumbnail_url`: `URLField(max_length=500, blank=True, help_text="Thumbnail preview URL")`
  - `caption`: `TextField(blank=True, help_text="Customer caption or quote")`
  - `uploader_name`: `CharField(max_length=120, blank=True)`
  - `uploader_handle`: `CharField(max_length=80, blank=True, help_text="@social_handle")`
  - `tagged_product`: `ForeignKey('ecommerce.CatalogProduct', on_delete=CASCADE, related_name='ugc_media')`
  - `tagged_variant`: `ForeignKey('ecommerce.ProductVariant', on_delete=SET_NULL, null=True, blank=True, related_name='ugc_media')`
  - `rights_status`: `CharField(max_length=25, choices=RIGHTS_STATUS_CHOICES, default='approved')`
  - `is_shoppable`: `BooleanField(default=True)`
  - `is_published`: `BooleanField(default=True)`
  - `display_order`: `PositiveIntegerField(default=10)`
  - `views_count`: `PositiveIntegerField(default=0)`
  - `clicks_count`: `PositiveIntegerField(default=0)`
  - `created_at`: `DateTimeField(auto_now_add=True)`
  - `updated_at`: `DateTimeField(auto_now=True)`
- **Constraints & Indexes:**
  - `UniqueConstraint(fields=['tenant', 'number'], name='ecommerce_eugc_tenant_num_uniq')`
  - `Index(fields=['tenant', 'tagged_product', 'is_published'], name='idx_eugc_ten_prod_pub')`
  - `Index(fields=['tenant', 'rights_status'], name='idx_eugc_ten_rights')`

---

### 1.4 `ReviewSentimentSummary` (`apps/ecommerce/models/ReviewUgc/ReviewSentimentSummaries.py`)
- **Table:** `ecommerce_review_sentiment_summary`
- **Number Prefix:** `ERVM` (`ERVM-00001`)
- **Fields:**
  - `tenant`: `ForeignKey('core.Tenant', on_delete=CASCADE, related_name='+')`
  - `number`: `CharField(max_length=20, editable=False)`
  - `product`: `OneToOneField('ecommerce.CatalogProduct', on_delete=CASCADE, related_name='review_summary')`
  - `total_reviews`: `PositiveIntegerField(default=0)`
  - `average_rating`: `DecimalField(max_digits=3, decimal_places=2, default=Decimal('0.00'))`
  - `rating_5_count`: `PositiveIntegerField(default=0)`
  - `rating_4_count`: `PositiveIntegerField(default=0)`
  - `rating_3_count`: `PositiveIntegerField(default=0)`
  - `rating_2_count`: `PositiveIntegerField(default=0)`
  - `rating_1_count`: `PositiveIntegerField(default=0)`
  - `positive_sentiment_pct`: `DecimalField(max_digits=5, decimal_places=2, default=Decimal('0.00'))`
  - `neutral_sentiment_pct`: `DecimalField(max_digits=5, decimal_places=2, default=Decimal('0.00'))`
  - `negative_sentiment_pct`: `DecimalField(max_digits=5, decimal_places=2, default=Decimal('0.00'))`
  - `top_positive_keywords`: `JSONField(default=list, blank=True, help_text="List of top praised attributes")`
  - `top_negative_keywords`: `JSONField(default=list, blank=True, help_text="List of top customer complaints")`
  - `improvement_recommendation`: `TextField(blank=True, help_text="Actionable quality guidance")`
  - `last_calculated_at`: `DateTimeField(auto_now=True)`
  - `created_at`: `DateTimeField(auto_now_add=True)`
  - `updated_at`: `DateTimeField(auto_now=True)`
- **Constraints & Indexes:**
  - `UniqueConstraint(fields=['tenant', 'number'], name='ecommerce_ervm_tenant_num_uniq')`
  - `Index(fields=['tenant', 'average_rating'], name='idx_ervm_ten_avg_rate')`
  - `Index(fields=['tenant', 'total_reviews'], name='idx_ervm_ten_tot_rev')`

---

## 2. Forms Contract

### 2.1 `ProductReviewForm`
- **Fields included:** `product`, `variant`, `customer`, `order`, `reviewer_name`, `reviewer_email`, `rating`, `title`, `body`, `status`, `sentiment`, `is_featured`, `merchant_response`, `moderation_note`
- **Exclusions:** `tenant`, `number`, `is_verified_purchase`, `helpful_votes`, `unhelpful_votes`, `sentiment_score`, `moderated_by`, `merchant_response_at`, `created_at`, `updated_at`

### 2.2 `ProductReviewModerationForm`
- **Fields included:** `status`, `sentiment`, `is_featured`, `merchant_response`, `moderation_note`

### 2.3 `ProductQuestionAnswerForm`
- **Fields included:** `product`, `author_name`, `author_email`, `customer`, `question_text`, `status`, `answer_text`, `answered_by_name`, `is_staff_answer`, `is_pinned`
- **Exclusions:** `tenant`, `number`, `answered_by_user`, `answered_at`, `helpful_votes`, `created_at`, `updated_at`

### 2.4 `VisualUgcMediaForm`
- **Fields included:** `media_type`, `media_url`, `thumbnail_url`, `caption`, `uploader_name`, `uploader_handle`, `tagged_product`, `tagged_variant`, `rights_status`, `is_shoppable`, `is_published`, `display_order`
- **Exclusions:** `tenant`, `number`, `views_count`, `clicks_count`, `created_at`, `updated_at`

### 2.5 `ReviewSentimentSummaryForm`
- **Fields included:** `product`, `improvement_recommendation`
- **Exclusions:** `tenant`, `number`, `total_reviews`, `average_rating`, `rating_5_count`, `rating_4_count`, `rating_3_count`, `rating_2_count`, `rating_1_count`, `positive_sentiment_pct`, `neutral_sentiment_pct`, `negative_sentiment_pct`, `last_calculated_at`, `created_at`, `updated_at`

---

## 3. URLs Contract

All URLs live under namespace `ecommerce:`:

```python
# ProductReview
path('reviews/', views.productreview_list, name='productreview_list'),
path('reviews/create/', views.productreview_create, name='productreview_create'),
path('reviews/<int:pk>/', views.productreview_detail, name='productreview_detail'),
path('reviews/<int:pk>/edit/', views.productreview_edit, name='productreview_edit'),
path('reviews/<int:pk>/delete/', views.productreview_delete, name='productreview_delete'),
path('reviews/<int:pk>/moderate/', views.productreview_moderate, name='productreview_moderate'),

# ProductQuestionAnswer
path('questions/', views.productquestionanswer_list, name='productquestionanswer_list'),
path('questions/create/', views.productquestionanswer_create, name='productquestionanswer_create'),
path('questions/<int:pk>/', views.productquestionanswer_detail, name='productquestionanswer_detail'),
path('questions/<int:pk>/edit/', views.productquestionanswer_edit, name='productquestionanswer_edit'),
path('questions/<int:pk>/delete/', views.productquestionanswer_delete, name='productquestionanswer_delete'),
path('questions/<int:pk>/respond/', views.productquestionanswer_respond, name='productquestionanswer_respond'),

# VisualUgcMedia
path('ugc/', views.visualugcmedia_list, name='visualugcmedia_list'),
path('ugc/create/', views.visualugcmedia_create, name='visualugcmedia_create'),
path('ugc/<int:pk>/', views.visualugcmedia_detail, name='visualugcmedia_detail'),
path('ugc/<int:pk>/edit/', views.visualugcmedia_edit, name='visualugcmedia_edit'),
path('ugc/<int:pk>/delete/', views.visualugcmedia_delete, name='visualugcmedia_delete'),

# ReviewSentimentSummary
path('sentiment/', views.reviewsentimentsummary_list, name='reviewsentimentsummary_list'),
path('sentiment/create/', views.reviewsentimentsummary_create, name='reviewsentimentsummary_create'),
path('sentiment/<int:pk>/', views.reviewsentimentsummary_detail, name='reviewsentimentsummary_detail'),
path('sentiment/<int:pk>/edit/', views.reviewsentimentsummary_edit, name='reviewsentimentsummary_edit'),
path('sentiment/<int:pk>/delete/', views.reviewsentimentsummary_delete, name='reviewsentimentsummary_delete'),
path('sentiment/<int:pk>/recalculate/', views.reviewsentimentsummary_recalculate, name='reviewsentimentsummary_recalculate'),
```

---

## 4. View Context Keys Contract (L7 Pinned)

### 4.1 `ProductReview` Views
- `productreview_list`:
  - Template: `ecommerce/review_ugc/product_review/list.html`
  - Context keys:
    - `reviews`: Paged queryset of `ProductReview`
    - `status_choices`: `ProductReview.STATUS_CHOICES`
    - `rating_choices`: `ProductReview.RATING_CHOICES`
    - `sentiment_choices`: `ProductReview.SENTIMENT_CHOICES`
    - `products`: Queryset of `CatalogProduct` for tenant
    - `selected_status`: `request.GET.get('status', '')`
    - `selected_rating`: `request.GET.get('rating', '')`
    - `selected_sentiment`: `request.GET.get('sentiment', '')`
    - `selected_product`: `request.GET.get('product', '')`
    - `query`: `request.GET.get('q', '')`
    - `page_obj`: Django page object
    - `paginator`: Paginator instance
- `productreview_detail`:
  - Template: `ecommerce/review_ugc/product_review/detail.html`
  - Context keys:
    - `review`: Single `ProductReview` instance
- `productreview_create` / `productreview_edit`:
  - Template: `ecommerce/review_ugc/product_review/form.html`
  - Context keys:
    - `form`: `ProductReviewForm`
    - `review`: `ProductReview` instance (edit) or `None` (create)
- `productreview_moderate`:
  - Template: `ecommerce/review_ugc/product_review/form.html`
  - Context keys:
    - `form`: `ProductReviewModerationForm`
    - `review`: `ProductReview` instance
    - `is_moderation`: `True`

### 4.2 `ProductQuestionAnswer` Views
- `productquestionanswer_list`:
  - Template: `ecommerce/review_ugc/product_question/list.html`
  - Context keys:
    - `questions`: Paged queryset of `ProductQuestionAnswer`
    - `status_choices`: `ProductQuestionAnswer.STATUS_CHOICES`
    - `products`: Queryset of `CatalogProduct` for tenant
    - `selected_status`: `request.GET.get('status', '')`
    - `selected_product`: `request.GET.get('product', '')`
    - `query`: `request.GET.get('q', '')`
    - `page_obj`: Django page object
    - `paginator`: Paginator instance
- `productquestionanswer_detail`:
  - Template: `ecommerce/review_ugc/product_question/detail.html`
  - Context keys:
    - `question`: Single `ProductQuestionAnswer` instance
- `productquestionanswer_create` / `productquestionanswer_edit`:
  - Template: `ecommerce/review_ugc/product_question/form.html`
  - Context keys:
    - `form`: `ProductQuestionAnswerForm`
    - `question`: `ProductQuestionAnswer` instance (edit) or `None` (create)
- `productquestionanswer_respond`:
  - Template: `ecommerce/review_ugc/product_question/form.html`
  - Context keys:
    - `form`: `ProductQuestionAnswerResponseForm`
    - `question`: `ProductQuestionAnswer` instance
    - `is_response`: `True`

### 4.3 `VisualUgcMedia` Views
- `visualugcmedia_list`:
  - Template: `ecommerce/review_ugc/visual_ugc/list.html`
  - Context keys:
    - `media_items`: Paged queryset of `VisualUgcMedia`
    - `media_type_choices`: `VisualUgcMedia.MEDIA_TYPE_CHOICES`
    - `rights_status_choices`: `VisualUgcMedia.RIGHTS_STATUS_CHOICES`
    - `products`: Queryset of `CatalogProduct` for tenant
    - `selected_media_type`: `request.GET.get('media_type', '')`
    - `selected_rights`: `request.GET.get('rights_status', '')`
    - `selected_product`: `request.GET.get('product', '')`
    - `query`: `request.GET.get('q', '')`
    - `page_obj`: Django page object
    - `paginator`: Paginator instance
- `visualugcmedia_detail`:
  - Template: `ecommerce/review_ugc/visual_ugc/detail.html`
  - Context keys:
    - `media_item`: Single `VisualUgcMedia` instance
- `visualugcmedia_create` / `visualugcmedia_edit`:
  - Template: `ecommerce/review_ugc/visual_ugc/form.html`
  - Context keys:
    - `form`: `VisualUgcMediaForm`
    - `media_item`: `VisualUgcMedia` instance (edit) or `None` (create)

### 4.4 `ReviewSentimentSummary` Views
- `reviewsentimentsummary_list`:
  - Template: `ecommerce/review_ugc/sentiment_summary/list.html`
  - Context keys:
    - `summaries`: Paged queryset of `ReviewSentimentSummary`
    - `products`: Queryset of `CatalogProduct` for tenant
    - `selected_product`: `request.GET.get('product', '')`
    - `query`: `request.GET.get('q', '')`
    - `page_obj`: Django page object
    - `paginator`: Paginator instance
- `reviewsentimentsummary_detail`:
  - Template: `ecommerce/review_ugc/sentiment_summary/detail.html`
  - Context keys:
    - `summary`: Single `ReviewSentimentSummary` instance
    - `recent_reviews`: Queryset of approved `ProductReview` for this product
- `reviewsentimentsummary_create` / `reviewsentimentsummary_edit`:
  - Template: `ecommerce/review_ugc/sentiment_summary/form.html`
  - Context keys:
    - `form`: `ReviewSentimentSummaryForm`
    - `summary`: `ReviewSentimentSummary` instance (edit) or `None` (create)

---

## 5. Templates Contract & Color Badges

All badges must strictly use theme.css colour-named classes (`badge-green`, `badge-red`, `badge-amber`, `badge-info`, `badge-muted`, `badge-slate`):

- **Review / Q&A Status**:
  - `'approved'`: `badge-green`
  - `'pending'`: `badge-amber`
  - `'rejected'`: `badge-red`
  - `'flagged_spam'`: `badge-slate`
- **Sentiment Status**:
  - `'positive'`: `badge-green`
  - `'neutral'`: `badge-info`
  - `'mixed'`: `badge-amber`
  - `'negative'`: `badge-red`
- **Visual UGC Rights Status**:
  - `'approved'`: `badge-green`
  - `'pending_request'`: `badge-amber`
  - `'rejected'`: `badge-red`
- **Verified Purchase**:
  - `badge-green` ("Verified Buyer")
- **Staff Answer**:
  - `badge-info` ("Official Staff")
- **Pinned / Featured**:
  - `badge-amber` ("Featured")
