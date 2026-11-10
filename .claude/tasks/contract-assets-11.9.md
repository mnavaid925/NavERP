# Contract — Sub-module 11.9: Asset Disposal & Retirement (Module 11: Asset Management System, `assets`)

- **Sub-module:** 11.9 Asset Disposal & Retirement • **Module:** 11 Asset Management System • **App:** `apps/assets`
- **Date:** 2026-11-10 • **Status:** FROZEN PRE-BUILD CONTRACT • **Phase:** 3.1 Spec
- **App Status:** Extending live `apps/assets/`. Incremental migration: `0012_...`.
- **Package Layout:** `AssetDisposal/` across `models/`, `forms/`, `views/`, `urls/`, and templates `templates/assets/assetdisposal/`.

---

## 1. Models & CHOICES Contract

All 4 models inherit from `apps.assets.models._base.TenantNumbered` (`tenant`, `number`, `created_at`, `updated_at`).

### 1.1 `AssetDisposalRequest` (`apps/assets/models/AssetDisposal/AssetDisposalRequests.py`)
- **Table:** `assets_assetdisposalrequest`
- **Number Prefix:** `ADSP` (format: `ADSP-YYYYMM-XXXX`)
- **CHOICES:**
  - `DISPOSAL_METHOD_CHOICES = [('resale', 'Commercial Resale / Auction'), ('trade_in', 'Vendor Trade-in / Exchange'), ('scrap_salvage', 'Scrap / Salvage & Recycling'), ('donation', 'Charitable Donation'), ('write_off_loss', 'Casualty Loss / Write-off')]`
  - `RETIREMENT_REASON_CHOICES = [('end_of_life', 'End of Useful Life'), ('uneconomical_repair', 'Uneconomical to Repair / Beyond Salvage'), ('technological_obsolescence', 'Technological Obsolescence'), ('damaged_accident', 'Accidental Damage / Total Loss'), ('lease_expired', 'Lease Term Expired'), ('redundant_surplus', 'Surplus / Facility Closure'), ('regulatory_compliance', 'Environmental / Safety Regulatory Mandate'), ('other', 'Other Business Justification')]`
  - `STATUS_CHOICES = [('draft', 'Draft (Initiated)'), ('submitted', 'Submitted for Review'), ('appraised', 'Appraised & Assessed'), ('approved', 'Approved for Disposal'), ('in_progress', 'Disposal in Progress'), ('completed', 'Disposal Completed & Closed'), ('rejected', 'Rejected'), ('cancelled', 'Cancelled')]`
  - `STATUS_CSS = {'draft': 'badge-slate', 'submitted': 'badge-amber', 'appraised': 'badge-info', 'approved': 'badge-green', 'in_progress': 'badge-info', 'completed': 'badge-green', 'rejected': 'badge-red', 'cancelled': 'badge-muted'}`
  - `DISPOSAL_METHOD_CSS = {'resale': 'badge-info', 'trade_in': 'badge-green', 'scrap_salvage': 'badge-amber', 'donation': 'badge-slate', 'write_off_loss': 'badge-red'}`
  - `RETIREMENT_REASON_CSS = {'end_of_life': 'badge-slate', 'uneconomical_repair': 'badge-amber', 'technological_obsolescence': 'badge-info', 'damaged_accident': 'badge-red', 'lease_expired': 'badge-slate', 'redundant_surplus': 'badge-muted', 'regulatory_compliance': 'badge-amber', 'other': 'badge-slate'}`
- **Fields:**
  - `tenant`: `ForeignKey('core.Tenant', on_delete=CASCADE, related_name='asset_disposal_requests')`
  - `number`: `CharField(max_length=32, editable=False)`
  - `title`: `CharField(max_length=255, help_text='Retirement initiative title or disposal summary')`
  - `fixed_asset`: `ForeignKey('accounting.FixedAsset', on_delete=CASCADE, related_name='disposal_requests', help_text='Financial Fixed Asset being retired')`
  - `operational_asset`: `ForeignKey('scm.Asset', on_delete=SET_NULL, null=True, blank=True, related_name='disposal_requests', help_text='Operational plant machinery or equipment record')`
  - `category`: `ForeignKey('assets.AssetCategory', on_delete=SET_NULL, null=True, blank=True, related_name='disposal_requests', help_text='Asset category classification')`
  - `cost_center`: `ForeignKey('core.OrgUnit', on_delete=SET_NULL, null=True, blank=True, related_name='asset_disposal_requests', help_text='Owning department or facility cost center')`
  - `requested_by`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=SET_NULL, null=True, blank=True, related_name='requested_asset_disposals', help_text='Initiating custodian or equipment engineer')`
  - `appraised_by`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=SET_NULL, null=True, blank=True, related_name='appraised_asset_disposals', help_text='Asset valuation specialist or technical appraiser')`
  - `approved_by`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=SET_NULL, null=True, blank=True, related_name='approved_asset_disposals', help_text='Authorizing corporate executive or finance manager')`
  - `accounting_disposal`: `ForeignKey('accounting.AssetDisposal', on_delete=SET_NULL, null=True, blank=True, related_name='asset_disposal_requests', help_text='Linked general ledger disposal transaction')`
  - `disposal_method`: `CharField(max_length=24, choices=DISPOSAL_METHOD_CHOICES, default='resale')`
  - `retirement_reason`: `CharField(max_length=32, choices=RETIREMENT_REASON_CHOICES, default='end_of_life')`
  - `justification_notes`: `TextField(help_text='Detailed justification for asset decommissioning')`
  - `acquisition_cost`: `DecimalField(max_digits=16, decimal_places=2, default=Decimal('0.00'), help_text='Original capitalized cost basis')`
  - `accumulated_depreciation`: `DecimalField(max_digits=16, decimal_places=2, default=Decimal('0.00'), help_text='Total depreciation booked to date')`
  - `net_book_value`: `DecimalField(max_digits=16, decimal_places=2, default=Decimal('0.00'), help_text='Current carrying value')`
  - `estimated_residual_value`: `DecimalField(max_digits=16, decimal_places=2, default=Decimal('0.00'), help_text='Appraised salvage or resale recovery value')`
  - `estimated_removal_cost`: `DecimalField(max_digits=16, decimal_places=2, default=Decimal('0.00'), help_text='Estimated decommissioning, teardown, or freight expense')`
  - `actual_gross_proceeds`: `DecimalField(max_digits=16, decimal_places=2, default=Decimal('0.00'), help_text='Gross realization from sale, trade-in, or scrap')`
  - `actual_removal_cost`: `DecimalField(max_digits=16, decimal_places=2, default=Decimal('0.00'), help_text='Incurred disposal, abatement, or dismantling fees')`
  - `realized_gain_loss`: `DecimalField(max_digits=16, decimal_places=2, default=Decimal('0.00'), help_text='Net financial gain (+) or loss (-) recognized upon disposal')`
  - `status`: `CharField(max_length=24, choices=STATUS_CHOICES, default='draft')`
  - `submitted_at`: `DateTimeField(null=True, blank=True)`
  - `approved_at`: `DateTimeField(null=True, blank=True)`
  - `completed_at`: `DateTimeField(null=True, blank=True)`
  - `rejection_reason`: `TextField(blank=True, help_text='Reason for rejection if authorization was declined')`
  - `created_at`: `DateTimeField(auto_now_add=True)`
  - `updated_at`: `DateTimeField(auto_now=True)`
- **Constraints & Indexes (L65 compliant <= 30 chars):**
  - `UniqueConstraint(fields=['tenant', 'number'], name='assets_adsp_ten_num_uniq')`
  - `Index(fields=['tenant', 'status'], name='idx_adsp_ten_stat')`
  - `Index(fields=['tenant', 'disposal_method'], name='idx_adsp_ten_meth')`
  - `Index(fields=['tenant', 'submitted_at'], name='idx_adsp_ten_subm')`
  - `Index(fields=['tenant', 'fixed_asset'], name='idx_adsp_ten_fa')`
- **Actions / State Machine:**
  - `asset_disposal_request_submit`: transitions `draft -> submitted`, sets `submitted_at = timezone.now()`.
  - `asset_disposal_request_appraise`: records appraiser appraisal and `estimated_residual_value`, transitions `submitted -> appraised`.
  - `asset_disposal_request_approve`: executive authorization, transitions `appraised -> approved`, sets `approved_at = timezone.now()`.
  - `asset_disposal_request_reject`: transitions to `rejected`, records `rejection_reason`.
  - `asset_disposal_request_complete`: completes retirement, sets `completed_at = timezone.now()`, updates `accounting.FixedAsset.status = 'disposed'`, advances `scm.Asset.status = 'disposed'`, recalculates `realized_gain_loss = actual_gross_proceeds - actual_removal_cost - net_book_value`, and transitions to `completed`.
- **Form exclusions:** `tenant`, `number`, `status`, `accounting_disposal`, `actual_gross_proceeds`, `actual_removal_cost`, `realized_gain_loss`, `submitted_at`, `approved_at`, `completed_at`, `rejection_reason`, `created_at`, `updated_at`.

---

### 1.2 `AssetResaleListing` (`apps/assets/models/AssetDisposal/AssetResaleListings.py`)
- **Table:** `assets_assetresalelisting`
- **Number Prefix:** `ARSL` (format: `ARSL-YYYYMM-XXXX`)
- **CHOICES:**
  - `LISTING_CHANNEL_CHOICES = [('public_auction', 'Industrial Auction (Public / Online)'), ('private_treaty', 'Private Treaty / Direct Negotiation'), ('online_marketplace', 'B2B Equipment Marketplace'), ('employee_sale', 'Internal Employee Purchase Program'), ('dealer_wholesale', 'Dealer Wholesale Liquidation')]`
  - `STATUS_CHOICES = [('draft', 'Draft Listing'), ('listed', 'Active on Market'), ('bid_received', 'Bid / Offer Received'), ('negotiation', 'Under Negotiation'), ('sold', 'Awarded / Sold'), ('payment_received', 'Payment Received & Reconciled'), ('delivered', 'Delivered / Asset Released'), ('unsold_withdrawn', 'Unsold / Listing Withdrawn'), ('cancelled', 'Cancelled')]`
  - `PAYMENT_STATUS_CHOICES = [('pending', 'Pending Invoicing / Escrow'), ('partial', 'Partial Deposit In Hand'), ('paid', 'Paid in Full'), ('waived', 'Waived / Written Off')]`
  - `STATUS_CSS = {'draft': 'badge-slate', 'listed': 'badge-info', 'bid_received': 'badge-amber', 'negotiation': 'badge-amber', 'sold': 'badge-green', 'payment_received': 'badge-green', 'delivered': 'badge-green', 'unsold_withdrawn': 'badge-muted', 'cancelled': 'badge-red'}`
  - `LISTING_CHANNEL_CSS = {'public_auction': 'badge-info', 'private_treaty': 'badge-slate', 'online_marketplace': 'badge-info', 'employee_sale': 'badge-green', 'dealer_wholesale': 'badge-slate'}`
  - `PAYMENT_STATUS_CSS = {'pending': 'badge-amber', 'partial': 'badge-amber', 'paid': 'badge-green', 'waived': 'badge-muted'}`
- **Fields:**
  - `tenant`: `ForeignKey('core.Tenant', on_delete=CASCADE, related_name='asset_resale_listings')`
  - `number`: `CharField(max_length=32, editable=False)`
  - `disposal_request`: `ForeignKey('assets.AssetDisposalRequest', on_delete=CASCADE, related_name='resale_listings', help_text='Parent disposal authorization request')`
  - `fixed_asset`: `ForeignKey('accounting.FixedAsset', on_delete=CASCADE, related_name='resale_listings', help_text='Fixed asset offered for resale')`
  - `buyer`: `ForeignKey('core.Party', on_delete=SET_NULL, null=True, blank=True, related_name='purchased_asset_listings', help_text='Winning buyer party record')`
  - `broker_auctioneer`: `ForeignKey('core.Party', on_delete=SET_NULL, null=True, blank=True, related_name='brokered_asset_listings', help_text='Remarketing broker or industrial auction house')`
  - `managed_by`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=SET_NULL, null=True, blank=True, related_name='managed_resale_listings', help_text='Internal asset remarketing manager')`
  - `bill_of_sale_document`: `ForeignKey('core.Document', on_delete=SET_NULL, null=True, blank=True, related_name='resale_bills_of_sale', help_text='Executed Bill of Sale or auction settlement statement')`
  - `listing_channel`: `CharField(max_length=24, choices=LISTING_CHANNEL_CHOICES, default='public_auction')`
  - `listing_reference`: `CharField(max_length=100, blank=True, help_text='External auction catalog lot number or portal listing ID')`
  - `listing_date`: `DateField(default=timezone.now, help_text='Date listing was published or auction cataloged')`
  - `closing_date`: `DateField(null=True, blank=True, help_text='Auction close or bidding deadline date')`
  - `reserve_price`: `DecimalField(max_digits=16, decimal_places=2, default=Decimal('0.00'), help_text='Confidential minimum reserve amount')`
  - `asking_price`: `DecimalField(max_digits=16, decimal_places=2, default=Decimal('0.00'), help_text='Public asking or target buy-it-now price')`
  - `highest_bid_amount`: `DecimalField(max_digits=16, decimal_places=2, default=Decimal('0.00'), help_text='Top standing offer or winning auction bid')`
  - `buyer_contact_name`: `CharField(max_length=150, blank=True, help_text='Name of buyer representative')`
  - `buyer_contact_email`: `CharField(max_length=254, blank=True, help_text='Buyer contact email')`
  - `buyer_contact_phone`: `CharField(max_length=50, blank=True, help_text='Buyer contact telephone')`
  - `gross_sale_proceeds`: `DecimalField(max_digits=16, decimal_places=2, default=Decimal('0.00'), help_text='Gross contract sale price agreed')`
  - `commission_rate_percent`: `DecimalField(max_digits=5, decimal_places=2, default=Decimal('0.00'), help_text='Auctioneer or broker commission percentage')`
  - `commission_amount`: `DecimalField(max_digits=16, decimal_places=2, default=Decimal('0.00'), help_text='Total commission deducted')`
  - `tax_amount`: `DecimalField(max_digits=16, decimal_places=2, default=Decimal('0.00'), help_text='Sales/transfer tax collected')`
  - `net_sale_proceeds`: `DecimalField(max_digits=16, decimal_places=2, default=Decimal('0.00'), help_text='Net proceeds received by seller (gross - commission)')`
  - `status`: `CharField(max_length=24, choices=STATUS_CHOICES, default='draft')`
  - `payment_status`: `CharField(max_length=20, choices=PAYMENT_STATUS_CHOICES, default='pending')`
  - `payment_date`: `DateField(null=True, blank=True, help_text='Date buyer remittance cleared')`
  - `pickup_delivery_date`: `DateField(null=True, blank=True, help_text='Date buyer collected equipment')`
  - `terms_and_conditions`: `TextField(blank=True, help_text='Special conditions of sale, warranty disclaimers, or pickup deadlines')`
  - `created_at`: `DateTimeField(auto_now_add=True)`
  - `updated_at`: `DateTimeField(auto_now=True)`
- **Constraints & Indexes (L65 compliant <= 30 chars):**
  - `UniqueConstraint(fields=['tenant', 'number'], name='assets_arsl_ten_num_uniq')`
  - `Index(fields=['tenant', 'status'], name='idx_arsl_ten_stat')`
  - `Index(fields=['tenant', 'listing_channel'], name='idx_arsl_ten_chan')`
  - `Index(fields=['tenant', 'listing_date'], name='idx_arsl_ten_ldate')`
- **Actions / State Machine:**
  - `asset_resale_listing_record_bid`: records highest received bid and prospective bidder party, advances `draft/listed -> bid_received`.
  - `asset_resale_listing_accept_sale`: locks winning sale offer, computes `commission_amount = gross_sale_proceeds * (commission_rate_percent / 100)` and `net_sale_proceeds = gross_sale_proceeds - commission_amount`, transitions to `sold`.
  - `asset_resale_listing_mark_paid`: records payment confirmation, sets `payment_status = 'paid'`, `payment_date = timezone.now().date()`, and synchronizes proceeds to parent `AssetDisposalRequest.actual_gross_proceeds`.
  - `asset_resale_listing_mark_delivered`: marks equipment picked up / freight dispatched, sets `pickup_delivery_date = timezone.now().date()`, transitions to `delivered`.
- **Form exclusions:** `tenant`, `number`, `status`, `payment_status`, `payment_date`, `pickup_delivery_date`, `commission_amount`, `net_sale_proceeds`, `created_at`, `updated_at`.

---

### 1.3 `AssetTradeIn` (`apps/assets/models/AssetDisposal/AssetTradeIns.py`)
- **Table:** `assets_assettradein`
- **Number Prefix:** `ATRD` (format: `ATRD-YYYYMM-XXXX`)
- **CHOICES:**
  - `STATUS_CHOICES = [('draft', 'Draft Proposal'), ('proposed', 'Submitted to Vendor'), ('negotiated', 'Valuation Negotiated'), ('accepted', 'Trade-in Approved & Bound'), ('equipment_surrendered', 'Equipment Handed Over to Vendor'), ('credit_settled', 'Allowance Settled on Invoice'), ('rejected', 'Trade-in Rejected'), ('cancelled', 'Cancelled')]`
  - `STATUS_CSS = {'draft': 'badge-slate', 'proposed': 'badge-amber', 'negotiated': 'badge-info', 'accepted': 'badge-info', 'equipment_surrendered': 'badge-amber', 'credit_settled': 'badge-green', 'rejected': 'badge-red', 'cancelled': 'badge-muted'}`
- **Fields:**
  - `tenant`: `ForeignKey('core.Tenant', on_delete=CASCADE, related_name='asset_trade_ins')`
  - `number`: `CharField(max_length=32, editable=False)`
  - `disposal_request`: `ForeignKey('assets.AssetDisposalRequest', on_delete=CASCADE, related_name='trade_ins', help_text='Parent disposal authorization request')`
  - `retired_fixed_asset`: `ForeignKey('accounting.FixedAsset', on_delete=CASCADE, related_name='trade_ins_retired', help_text='Retiring fixed asset being traded in')`
  - `vendor`: `ForeignKey('core.Party', on_delete=PROTECT, related_name='asset_trade_in_vendors', help_text='OEM dealer or machinery supplier offering trade credit')`
  - `replacement_requisition`: `ForeignKey('assets.AssetRequisition', on_delete=SET_NULL, null=True, blank=True, related_name='trade_ins', help_text='Linked purchase requisition for replacement machine')`
  - `replacement_fixed_asset`: `ForeignKey('accounting.FixedAsset', on_delete=SET_NULL, null=True, blank=True, related_name='trade_ins_replacement', help_text='New replacement asset acquired in exchange')`
  - `authorized_by`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=SET_NULL, null=True, blank=True, related_name='authorized_asset_trade_ins', help_text='Procurement or finance manager authorizing trade')`
  - `agreement_document`: `ForeignKey('core.Document', on_delete=SET_NULL, null=True, blank=True, related_name='trade_in_agreements', help_text='Executed dealer exchange contract or credit memo')`
  - `agreement_number`: `CharField(max_length=100, blank=True, help_text='Vendor exchange agreement reference number')`
  - `agreement_date`: `DateField(default=timezone.now, help_text='Date of trade-in agreement signing')`
  - `handover_due_date`: `DateField(null=True, blank=True, help_text='Target deadline for releasing physical asset to dealer')`
  - `dealer_appraised_value`: `DecimalField(max_digits=16, decimal_places=2, default=Decimal('0.00'), help_text='Dealer wholesale appraised value')`
  - `trade_in_allowance`: `DecimalField(max_digits=16, decimal_places=2, default=Decimal('0.00'), help_text='Contractual trade allowance credited against new purchase')`
  - `over_allowance_amount`: `DecimalField(max_digits=16, decimal_places=2, default=Decimal('0.00'), help_text='Dealer marketing incentive / over-allowance discount')`
  - `net_credit_applied`: `DecimalField(max_digits=16, decimal_places=2, default=Decimal('0.00'), help_text='Total net credit offset against replacement cost (allowance + over-allowance)')`
  - `replacement_asset_cost`: `DecimalField(max_digits=16, decimal_places=2, default=Decimal('0.00'), help_text='Gross purchase cost of new replacement asset')`
  - `net_cash_outflow`: `DecimalField(max_digits=16, decimal_places=2, default=Decimal('0.00'), help_text='Net remaining cash payment due (replacement cost - net credit)')`
  - `like_kind_exchange`: `BooleanField(default=False, help_text='Flags transaction as IRC Sec 1031 / like-kind exchange for deferred tax gain/loss')`
  - `gain_loss_deferred`: `DecimalField(max_digits=16, decimal_places=2, default=Decimal('0.00'), help_text='Taxable gain/loss deferred into replacement basis')`
  - `status`: `CharField(max_length=24, choices=STATUS_CHOICES, default='draft')`
  - `surrendered_at`: `DateTimeField(null=True, blank=True, help_text='Timestamp physical equipment was transferred')`
  - `settled_at`: `DateTimeField(null=True, blank=True, help_text='Timestamp trade credit was cleared on dealer invoice')`
  - `notes`: `TextField(blank=True, help_text='Exchange stipulations, freight terms, or warranty offset notes')`
  - `created_at`: `DateTimeField(auto_now_add=True)`
  - `updated_at`: `DateTimeField(auto_now=True)`
- **Constraints & Indexes (L65 compliant <= 30 chars):**
  - `UniqueConstraint(fields=['tenant', 'number'], name='assets_atrd_ten_num_uniq')`
  - `Index(fields=['tenant', 'status'], name='idx_atrd_ten_stat')`
  - `Index(fields=['tenant', 'agreement_date'], name='idx_atrd_ten_adate')`
  - `Index(fields=['tenant', 'vendor'], name='idx_atrd_ten_vend')`
- **Actions / State Machine:**
  - Auto-computes `net_credit_applied = trade_in_allowance + over_allowance_amount` and `net_cash_outflow = max(Decimal('0.00'), replacement_asset_cost - net_credit_applied)`.
  - `asset_trade_in_surrender`: logs equipment surrender timestamp, transitions status to `equipment_surrendered`.
  - `asset_trade_in_settle`: confirms credit applied, transitions status to `credit_settled`, sets `settled_at = timezone.now()`, and updates parent `AssetDisposalRequest.actual_gross_proceeds` with the net trade credit.
- **Form exclusions:** `tenant`, `number`, `status`, `net_credit_applied`, `net_cash_outflow`, `surrendered_at`, `settled_at`, `created_at`, `updated_at`.

---

### 1.4 `AssetScrapSalvage` (`apps/assets/models/AssetDisposal/AssetScrapSalvages.py`)
- **Table:** `assets_assetscrapsalvage`
- **Number Prefix:** `ASCR` (format: `ASCR-YYYYMM-XXXX`)
- **CHOICES:**
  - `SCRAP_METHOD_CHOICES = [('physical_destruction', 'Physical Crushing / Destruction On-Site'), ('dismantling_parts_recovery', 'Controlled Teardown & Spare Parts Harvesting'), ('shredding_recycling', 'Industrial Scrap Metal Shredding'), ('e_waste_itad', 'Certified ITAD / Electronic Scrap Refining'), ('hazardous_waste_abatement', 'Hazardous Materials Remediation & Destruction')]`
  - `STATUS_CHOICES = [('draft', 'Draft Work Order'), ('dismantling', 'Dismantling & Sorting In Progress'), ('abatement_in_progress', 'Hazardous Waste Abatement'), ('scrap_transferred', 'Transferred to Recycler Yard'), ('certified_destroyed', 'Destruction Certified (CoD on File)'), ('settled', 'Scrap Settlement Closed'), ('cancelled', 'Cancelled')]`
  - `SANITIZATION_METHOD_CHOICES = [('none', 'Not Applicable / Non-Electronic Asset'), ('nist_clear', 'NIST SP 800-88 Clear (Logical Overwrite)'), ('nist_purge', 'NIST SP 800-88 Purge (Cryptographic / Degauss)'), ('dod_5220_wipe', 'DoD 5220.22-M Multi-Pass Wipe'), ('physical_shredding', 'Mechanical Drive Puncture / Shredding'), ('crypto_erase', 'SED Cryptographic Erase')]`
  - `STATUS_CSS = {'draft': 'badge-slate', 'dismantling': 'badge-amber', 'abatement_in_progress': 'badge-amber', 'scrap_transferred': 'badge-info', 'certified_destroyed': 'badge-green', 'settled': 'badge-green', 'cancelled': 'badge-red'}`
  - `SCRAP_METHOD_CSS = {'physical_destruction': 'badge-red', 'dismantling_parts_recovery': 'badge-info', 'shredding_recycling': 'badge-slate', 'e_waste_itad': 'badge-info', 'hazardous_waste_abatement': 'badge-amber'}`
  - `SANITIZATION_METHOD_CSS = {'none': 'badge-slate', 'nist_clear': 'badge-info', 'nist_purge': 'badge-green', 'dod_5220_wipe': 'badge-green', 'physical_shredding': 'badge-red', 'crypto_erase': 'badge-info'}`
- **Fields:**
  - `tenant`: `ForeignKey('core.Tenant', on_delete=CASCADE, related_name='asset_scrap_salvages')`
  - `number`: `CharField(max_length=32, editable=False)`
  - `disposal_request`: `ForeignKey('assets.AssetDisposalRequest', on_delete=CASCADE, related_name='scrap_salvages', help_text='Parent disposal authorization request')`
  - `fixed_asset`: `ForeignKey('accounting.FixedAsset', on_delete=CASCADE, related_name='scrap_salvages', help_text='Fixed asset being scrapped')`
  - `operational_asset`: `ForeignKey('scm.Asset', on_delete=SET_NULL, null=True, blank=True, related_name='scrap_salvages', help_text='Operational plant machinery decommissioned')`
  - `recycler_partner`: `ForeignKey('core.Party', on_delete=SET_NULL, null=True, blank=True, related_name='asset_scrap_recyclers', help_text='Licensed scrap processor, metal foundry, or certified ITAD partner')`
  - `supervisor`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=SET_NULL, null=True, blank=True, related_name='supervised_asset_scraps', help_text='Plant decommissioning supervisor or safety officer')`
  - `certificate_of_destruction`: `ForeignKey('core.Document', on_delete=SET_NULL, null=True, blank=True, related_name='scrap_destruction_certificates', help_text='Attached certified Certificate of Destruction (CoD)')`
  - `hazardous_manifest_doc`: `ForeignKey('core.Document', on_delete=SET_NULL, null=True, blank=True, related_name='scrap_hazardous_manifests', help_text='EPA Uniform Hazardous Waste Manifest or e-Waste consignment document')`
  - `scrap_method`: `CharField(max_length=32, choices=SCRAP_METHOD_CHOICES, default='dismantling_parts_recovery')`
  - `decommissioning_date`: `DateField(default=timezone.now, help_text='Date equipment decommissioning commenced')`
  - `completion_date`: `DateField(null=True, blank=True, help_text='Date scrapping and metal recycling concluded')`
  - `total_scrap_weight_kg`: `DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'), help_text='Gross weight of scrapped machinery in kilograms')`
  - `ferrous_weight_kg`: `DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'), help_text='Recovered carbon steel / cast iron scrap weight (kg)')`
  - `non_ferrous_weight_kg`: `DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'), help_text='Recovered copper, aluminum, brass, or stainless scrap weight (kg)')`
  - `e_waste_weight_kg`: `DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'), help_text='Printed circuit boards, drives, and electronic scrap weight (kg)')`
  - `salvage_proceeds`: `DecimalField(max_digits=16, decimal_places=2, default=Decimal('0.00'), help_text='Gross settlement revenue received from scrap metal dealer')`
  - `dismantling_cost`: `DecimalField(max_digits=16, decimal_places=2, default=Decimal('0.00'), help_text='Contractor teardown, crane hire, rigging, or hazardous abatement fees')`
  - `net_salvage_recovery`: `DecimalField(max_digits=16, decimal_places=2, default=Decimal('0.00'), help_text='Net financial recovery from salvage (proceeds - dismantling cost)')`
  - `has_hazardous_materials`: `BooleanField(default=False, help_text='Flags equipment containing PCB oils, mercury switches, asbestos, lead, refrigerants, or heavy metals')`
  - `hazardous_waste_class`: `CharField(max_length=50, blank=True, help_text='EPA/RCRA hazardous waste classification code')`
  - `epa_manifest_number`: `CharField(max_length=100, blank=True, help_text='State/federal tracking number on uniform hazardous waste manifest')`
  - `abatement_certified`: `BooleanField(default=False, help_text='Verified that environmental contaminants have been professionally mitigated')`
  - `abatement_date`: `DateField(null=True, blank=True, help_text='Date environmental remediation clearance was issued')`
  - `data_sanitized`: `BooleanField(default=False, help_text='Verified that persistent media has undergone certified data wiping or physical degauss/shredding')`
  - `sanitization_method`: `CharField(max_length=30, choices=SANITIZATION_METHOD_CHOICES, default='none')`
  - `sanitization_verified_by`: `CharField(max_length=150, blank=True, help_text='Name and credentials of IT security / ITAD auditor')`
  - `cod_number`: `CharField(max_length=100, blank=True, help_text='Serial number printed on official Certificate of Destruction')`
  - `cod_issue_date`: `DateField(null=True, blank=True, help_text='Date Certificate of Destruction was executed')`
  - `cod_issuing_agency`: `CharField(max_length=150, blank=True, help_text='Authorized commercial recycling partner issuing destruction certificate')`
  - `carrier_name`: `CharField(max_length=150, blank=True, help_text='Hauling contractor transporting scrap')`
  - `bill_of_lading_number`: `CharField(max_length=100, blank=True, help_text='Bill of Lading / weigh scale ticket reference')`
  - `notes`: `TextField(blank=True, help_text='Dismantling notes, recovered spare parts serials, or recycling log details')`
  - `status`: `CharField(max_length=24, choices=STATUS_CHOICES, default='draft')`
  - `created_at`: `DateTimeField(auto_now_add=True)`
  - `updated_at`: `DateTimeField(auto_now=True)`
- **Constraints & Indexes (L65 compliant <= 30 chars):**
  - `UniqueConstraint(fields=['tenant', 'number'], name='assets_ascr_ten_num_uniq')`
  - `Index(fields=['tenant', 'status'], name='idx_ascr_ten_stat')`
  - `Index(fields=['tenant', 'scrap_method'], name='idx_ascr_ten_meth')`
  - `Index(fields=['tenant', 'decommissioning_date'], name='idx_ascr_ten_dcdate')`
  - `Index(fields=['tenant', 'has_hazardous_materials'], name='idx_ascr_ten_haz')`
- **Actions / State Machine:**
  - Auto-computes `net_salvage_recovery = salvage_proceeds - dismantling_cost`.
  - `asset_scrap_salvage_certify_abatement`: sets `abatement_certified = True`, `abatement_date = timezone.now().date()`, transitions to `scrap_transferred`.
  - `asset_scrap_salvage_record_cod`: records CoD number and issuing agency, transitions to `certified_destroyed`.
  - `asset_scrap_salvage_settle`: computes net salvage recovery, sets `completion_date = timezone.now().date()`, transitions to `settled`, and updates parent `AssetDisposalRequest.actual_gross_proceeds` with `salvage_proceeds` and `actual_removal_cost` with `dismantling_cost`.
- **Form exclusions:** `tenant`, `number`, `status`, `net_salvage_recovery`, `abatement_date`, `completion_date`, `created_at`, `updated_at`.

---

## 2. Forms Contract (`apps/assets/forms/AssetDisposal/`)

### 2.1 `AssetDisposalRequestForm`
- **Model:** `AssetDisposalRequest`
- **Fields:** `title`, `fixed_asset`, `operational_asset`, `category`, `cost_center`, `requested_by`, `appraised_by`, `approved_by`, `disposal_method`, `retirement_reason`, `justification_notes`, `acquisition_cost`, `accumulated_depreciation`, `net_book_value`, `estimated_residual_value`, `estimated_removal_cost`
- **Widgets:** Selects styled with `form-select`, text/number inputs styled with `form-input`, textareas styled with `form-textarea`. `fixed_asset`, `operational_asset`, `category`, `cost_center`, and user FKs filtered by `tenant`.
- **Custom Methods / Clean:** Auto-populate `acquisition_cost`, `accumulated_depreciation`, and `net_book_value` from selected `fixed_asset` if left blank or 0.

### 2.2 `AssetResaleListingForm`
- **Model:** `AssetResaleListing`
- **Fields:** `disposal_request`, `fixed_asset`, `listing_channel`, `listing_reference`, `listing_date`, `closing_date`, `reserve_price`, `asking_price`, `highest_bid_amount`, `buyer`, `broker_auctioneer`, `managed_by`, `bill_of_sale_document`, `buyer_contact_name`, `buyer_contact_email`, `buyer_contact_phone`, `gross_sale_proceeds`, `commission_rate_percent`, `tax_amount`, `terms_and_conditions`
- **Widgets:** Dates use `type='date'` inputs. All selects/inputs styled with standard Tailwind form classes.

### 2.3 `AssetTradeInForm`
- **Model:** `AssetTradeIn`
- **Fields:** `disposal_request`, `retired_fixed_asset`, `vendor`, `replacement_requisition`, `replacement_fixed_asset`, `authorized_by`, `agreement_document`, `agreement_number`, `agreement_date`, `handover_due_date`, `dealer_appraised_value`, `trade_in_allowance`, `over_allowance_amount`, `replacement_asset_cost`, `like_kind_exchange`, `gain_loss_deferred`, `notes`
- **Widgets:** Dates use `type='date'` inputs. Checkbox uses `form-checkbox`.

### 2.4 `AssetScrapSalvageForm`
- **Model:** `AssetScrapSalvage`
- **Fields:** `disposal_request`, `fixed_asset`, `operational_asset`, `recycler_partner`, `supervisor`, `certificate_of_destruction`, `hazardous_manifest_doc`, `scrap_method`, `decommissioning_date`, `total_scrap_weight_kg`, `ferrous_weight_kg`, `non_ferrous_weight_kg`, `e_waste_weight_kg`, `salvage_proceeds`, `dismantling_cost`, `has_hazardous_materials`, `hazardous_waste_class`, `epa_manifest_number`, `abatement_certified`, `data_sanitized`, `sanitization_method`, `sanitization_verified_by`, `cod_number`, `cod_issue_date`, `cod_issuing_agency`, `carrier_name`, `bill_of_lading_number`, `notes`
- **Widgets:** Standard form inputs and date pickers.

---

## 3. URLs & Routing Contract (`apps/assets/urls/AssetDisposal/`)

All URL patterns live under app namespace `assets:`:

### 3.1 `AssetDisposalRequest` Routes
- `disposal/requests/` -> `assets:asset_disposal_request_list`
- `disposal/requests/create/` -> `assets:asset_disposal_request_create`
- `disposal/requests/<int:pk>/` -> `assets:asset_disposal_request_detail`
- `disposal/requests/<int:pk>/edit/` -> `assets:asset_disposal_request_edit`
- `disposal/requests/<int:pk>/delete/` -> `assets:asset_disposal_request_delete`
- `disposal/requests/<int:pk>/submit/` -> `assets:asset_disposal_request_submit`
- `disposal/requests/<int:pk>/appraise/` -> `assets:asset_disposal_request_appraise`
- `disposal/requests/<int:pk>/approve/` -> `assets:asset_disposal_request_approve`
- `disposal/requests/<int:pk>/reject/` -> `assets:asset_disposal_request_reject`
- `disposal/requests/<int:pk>/complete/` -> `assets:asset_disposal_request_complete`

### 3.2 `AssetResaleListing` Routes
- `disposal/resale-listings/` -> `assets:asset_resale_listing_list`
- `disposal/resale-listings/create/` -> `assets:asset_resale_listing_create`
- `disposal/resale-listings/<int:pk>/` -> `assets:asset_resale_listing_detail`
- `disposal/resale-listings/<int:pk>/edit/` -> `assets:asset_resale_listing_edit`
- `disposal/resale-listings/<int:pk>/delete/` -> `assets:asset_resale_listing_delete`
- `disposal/resale-listings/<int:pk>/record-bid/` -> `assets:asset_resale_listing_record_bid`
- `disposal/resale-listings/<int:pk>/accept-sale/` -> `assets:asset_resale_listing_accept_sale`
- `disposal/resale-listings/<int:pk>/mark-paid/` -> `assets:asset_resale_listing_mark_paid`
- `disposal/resale-listings/<int:pk>/mark-delivered/` -> `assets:asset_resale_listing_mark_delivered`

### 3.3 `AssetTradeIn` Routes
- `disposal/trade-ins/` -> `assets:asset_trade_in_list`
- `disposal/trade-ins/create/` -> `assets:asset_trade_in_create`
- `disposal/trade-ins/<int:pk>/` -> `assets:asset_trade_in_detail`
- `disposal/trade-ins/<int:pk>/edit/` -> `assets:asset_trade_in_edit`
- `disposal/trade-ins/<int:pk>/delete/` -> `assets:asset_trade_in_delete`
- `disposal/trade-ins/<int:pk>/surrender/` -> `assets:asset_trade_in_surrender`
- `disposal/trade-ins/<int:pk>/settle/` -> `assets:asset_trade_in_settle`

### 3.4 `AssetScrapSalvage` Routes
- `disposal/scrap-salvages/` -> `assets:asset_scrap_salvage_list`
- `disposal/scrap-salvages/create/` -> `assets:asset_scrap_salvage_create`
- `disposal/scrap-salvages/<int:pk>/` -> `assets:asset_scrap_salvage_detail`
- `disposal/scrap-salvages/<int:pk>/edit/` -> `assets:asset_scrap_salvage_edit`
- `disposal/scrap-salvages/<int:pk>/delete/` -> `assets:asset_scrap_salvage_delete`
- `disposal/scrap-salvages/<int:pk>/certify-abatement/` -> `assets:asset_scrap_salvage_certify_abatement`
- `disposal/scrap-salvages/<int:pk>/record-cod/` -> `assets:asset_scrap_salvage_record_cod`
- `disposal/scrap-salvages/<int:pk>/settle/` -> `assets:asset_scrap_salvage_settle`

---

## 4. View Context Keys Contract

### 4.1 `AssetDisposalRequest`
- **List View (`asset_disposal_request_list`)**:
  - `disposal_requests`: Paginated list of requests.
  - `page_obj`, `paginator`, `is_paginated`: Standard Django pagination.
  - `status_choices`: From `AssetDisposalRequest.STATUS_CHOICES`.
  - `method_choices`: From `AssetDisposalRequest.DISPOSAL_METHOD_CHOICES`.
  - `reason_choices`: From `AssetDisposalRequest.RETIREMENT_REASON_CHOICES`.
  - `category_list`: Filter queryset of `AssetCategory.objects.filter(tenant=request.tenant)`.
  - `total_requests`: Total count of tenant disposal requests.
  - `pending_approval_count`: Count with status in `['submitted', 'appraised']`.
  - `in_progress_count`: Count with status `in_progress`.
  - `completed_count`: Count with status `completed`.
  - `total_gain_loss`: Sum of `realized_gain_loss`.
- **Detail View (`asset_disposal_request_detail`)**:
  - `disposal_request`: The instance.
  - `resale_listings`: Related listings (`disposal_request.resale_listings.all()`).
  - `trade_ins`: Related trade-in records (`disposal_request.trade_ins.all()`).
  - `scrap_salvages`: Related scrap salvage records (`disposal_request.scrap_salvages.all()`).
- **Form View (`asset_disposal_request_form`)**:
  - `form`: ModelForm instance.
  - `disposal_request`: Instance if editing, else `None`.
  - `is_edit`: Boolean indicating update mode.

### 4.2 `AssetResaleListing`
- **List View (`asset_resale_listing_list`)**:
  - `resale_listings`: Paginated list of listings.
  - `page_obj`, `paginator`, `is_paginated`: Standard Django pagination.
  - `status_choices`: From `AssetResaleListing.STATUS_CHOICES`.
  - `channel_choices`: From `AssetResaleListing.LISTING_CHANNEL_CHOICES`.
  - `payment_status_choices`: From `AssetResaleListing.PAYMENT_STATUS_CHOICES`.
  - `total_listings`: Total count.
  - `active_listings_count`: Count with status in `['listed', 'bid_received', 'negotiation']`.
  - `sold_count`: Count with status in `['sold', 'payment_received', 'delivered']`.
  - `total_realized_proceeds`: Sum of `net_sale_proceeds`.
- **Detail View (`asset_resale_listing_detail`)**:
  - `resale_listing`: The instance.
- **Form View (`asset_resale_listing_form`)**:
  - `form`: ModelForm instance.
  - `resale_listing`: Instance if editing, else `None`.
  - `is_edit`: Boolean indicating update mode.

### 4.3 `AssetTradeIn`
- **List View (`asset_trade_in_list`)**:
  - `trade_ins`: Paginated list of trade-ins.
  - `page_obj`, `paginator`, `is_paginated`: Standard Django pagination.
  - `status_choices`: From `AssetTradeIn.STATUS_CHOICES`.
  - `vendor_list`: Filter queryset of `core.Party.objects.filter(tenant=request.tenant)`.
  - `total_trade_ins`: Total count.
  - `pending_handover_count`: Count with status in `['proposed', 'negotiated', 'accepted']`.
  - `settled_count`: Count with status `credit_settled`.
  - `total_trade_credit`: Sum of `net_credit_applied`.
- **Detail View (`asset_trade_in_detail`)**:
  - `trade_in`: The instance.
- **Form View (`asset_trade_in_form`)**:
  - `form`: ModelForm instance.
  - `trade_in`: Instance if editing, else `None`.
  - `is_edit`: Boolean indicating update mode.

### 4.4 `AssetScrapSalvage`
- **List View (`asset_scrap_salvage_list`)**:
  - `scrap_salvages`: Paginated list of scrap jobs.
  - `page_obj`, `paginator`, `is_paginated`: Standard Django pagination.
  - `status_choices`: From `AssetScrapSalvage.STATUS_CHOICES`.
  - `scrap_method_choices`: From `AssetScrapSalvage.SCRAP_METHOD_CHOICES`.
  - `recycler_list`: Filter queryset of `core.Party.objects.filter(tenant=request.tenant)`.
  - `total_scraps`: Total count.
  - `in_progress_count`: Count with status in `['dismantling', 'abatement_in_progress', 'scrap_transferred']`.
  - `certified_destroyed_count`: Count with status in `['certified_destroyed', 'settled']`.
  - `total_salvage_proceeds`: Sum of `salvage_proceeds`.
  - `total_weight_recovered`: Sum of `total_scrap_weight_kg`.
- **Detail View (`asset_scrap_salvage_detail`)**:
  - `scrap_salvage`: The instance.
- **Form View (`asset_scrap_salvage_form`)**:
  - `form`: ModelForm instance.
  - `scrap_salvage`: Instance if editing, else `None`.
  - `is_edit`: Boolean indicating update mode.

---

## 5. Templates Contract (`templates/assets/assetdisposal/`)

Templates follow the standard NavERP Tailwind/design-system hierarchy:
```
templates/assets/assetdisposal/
  asset_disposal_request/
    list.html
    detail.html
    form.html
  asset_resale_listing/
    list.html
    detail.html
    form.html
  asset_trade_in/
    list.html
    detail.html
    form.html
  asset_scrap_salvage/
    list.html
    detail.html
    form.html
```

- Badges strictly use color-named CSS classes: `badge-green`, `badge-red`, `badge-amber`, `badge-info`, `badge-muted`, `badge-slate`.
- Stat icons strictly use: `blue`, `green`, `orange`, `purple`, `slate`.
- Filter comparisons for FK/pk strictly use `|stringformat:"d"`.
- Pagination uses `has_previous` and `has_next` guards.
- Modals or action forms for transitions: POST-only with `{% csrf_token %}` and confirm dialogs.

---

## 6. Navigation Wiring Contract (`apps/core/navigation.py`)

`LIVE_LINKS["11.9"]`:
```python
    "11.9": {
        "Disposal Request & Approval": "assets:asset_disposal_request_list",
        "Asset Resale & Auction": "assets:asset_resale_listing_list",
        "Trade-in & Exchange Programs": "assets:asset_trade_in_list",
        "Scrap & Salvage Management": "assets:asset_scrap_salvage_list",
        "Disposal Documentation & Compliance": "assets:asset_scrap_salvage_list",
        # Plural and convenience aliases
        "Disposal Requests": "assets:asset_disposal_request_list",
        "Asset Disposal Requests": "assets:asset_disposal_request_list",
        "Resale & Auction": "assets:asset_resale_listing_list",
        "Asset Resale Listings": "assets:asset_resale_listing_list",
        "Trade-in & Exchange": "assets:asset_trade_in_list",
        "Asset Trade-Ins": "assets:asset_trade_in_list",
        "Scrap & Salvage": "assets:asset_scrap_salvage_list",
        "Asset Scrap & Salvage": "assets:asset_scrap_salvage_list",
        "Certificates of Destruction": "assets:asset_scrap_salvage_list",
        "Asset Disposal & Retirement": "assets:asset_disposal_request_list",
    },
```

---

## 7. Audit Logging & Security Contract
- Every create, update, delete, and state transition invokes:
  `write_audit_log(request.user, instance, "create"|"update"|"delete", tenant=request.tenant)`
- Strict multi-tenancy: Every query filters by `tenant=request.tenant`. Cross-tenant IDOR returns 404.
