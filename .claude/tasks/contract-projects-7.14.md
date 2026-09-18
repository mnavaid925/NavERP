# Build Contract — Projects 7.14 Client & External Collaboration (`projects`)

> Frozen 2026-09-18 against the live tree at commit `4481e2c9`.
> This contract is the single source of truth for the entity-by-entity build.
> Every variable name, field name, URL name, context key, and badge class is pinned here.

---

## 0. Scope & Capability Coverage

Five NavERP.md 7.14 capability bullets mapped to 5 primary entities + 1 amendment child model:

| Bullet | What 7.14 Owns | Artifacts |
|---|---|---|
| **Client Portal & Visibility** | Branded client access, permission flags, token generation, external visibility management | `ClientPortalAccess` [`CPA-`] (`ClientPortals.py`) |
| **Client Feedback & Approvals** | Deliverable review cycles, feedback capture, annotations, formal sign-off workflow | `ClientApprovalRequest` [`CFB-`] (`ClientFeedbacks.py`) |
| **Contract & SOW Management** | Statement of work authoring, billing terms, amendment history, contract lifecycle | `StatementOfWork` [`SOW-`] + `SOWAmendment` [`SWA-`] (`StatementOfWorks.py`) |
| **External Vendor Coordination** | Subcontractor task assignments, deliverable handoffs, delivery receipt, vendor scorecard (1-5) | `VendorHandoff` [`VHD-`] (`VendorHandoffs.py`) |
| **Billing & Invoicing to Clients** | Fixed-fee, T&M, milestone billing schedule, linkage to `accounting.Invoice` | `ProjectClientInvoice` [`PCI-`] (`ClientInvoices.py`) |

### Non-Goals & Invariants
- **Accounting owns the financial ledger (L29/L36)**: `ProjectClientInvoice` does NOT create a second AR table. It acts as the delivery billing schedule and milestone generator which links to or creates draft `accounting.Invoice` instances.
- **Staff pages in sidebar (L32)**: All five NavERP.md bullets map to staff-facing management pages, never external client login-gated URLs.
- **Core Party reuse (L28)**: Clients and external vendors are `core.Party` records.
- **Audit action strings ≤ 10 characters**: `create`, `update`, `delete`, `approve`, `reject`, `activate`, `bill`.
- **Badges strictly colour-named (L33)**: `badge-green`, `badge-red`, `badge-amber`, `badge-info`, `badge-muted`, `badge-slate`.

---

## 1. Verified Ground Truth

- `Project` [`PRJ-`] (`apps/projects/models/ProjectInitiation/Projects.py`), url name `projects:prj_detail`.
- `ProjectMilestone` [`MST-`] (`apps/projects/models/ProjectPlanningScheduling/ProjectMilestones.py`), url name `projects:mst_detail`.
- `ProjectTask` [`TSK-`] (`apps/projects/models/ProjectPlanningScheduling/ProjectTasks.py`), url name `projects:tsk_detail`.
- `accounting.Currency` (Global, no tenant FK), `accounting.Invoice` (`apps/accounting/models/AccountsReceivable/Invoices.py`).
- `TenantNumbered`, `TenantOwned`, `q2`, `ZERO` (`apps/projects/models/_base.py`).
- `TenantModelForm`, `_reject_foreign` (`apps/projects/forms/_common.py`).
- `crud_list`, `crud_detail`, `crud_create`, `crud_edit`, `crud_delete` (`apps/core/crud.py`).
- `write_audit_log` (`apps/core/utils.py`).

---

## 2. Model & Form Specifications

### 2.1 Entity 1: `ClientPortalAccess` [`CPA-`] (`apps/projects/models/ClientExternalCollaboration/ClientPortals.py`)
- Base: `TenantNumbered`, `NUMBER_PREFIX = "CPA"`
- Fields:
  - `project`: `ForeignKey("projects.Project", on_delete=models.CASCADE, related_name="client_portal_accesses")`
  - `client_contact`: `ForeignKey("core.Party", on_delete=models.CASCADE, related_name="project_portal_accesses")`
  - `portal_user`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="project_portal_accesses")`
  - `access_token`: `UUIDField(default=uuid.uuid4, editable=False, unique=True)`
  - `can_view_progress`: `BooleanField(default=True)`
  - `can_view_milestones`: `BooleanField(default=True)`
  - `can_view_deliverables`: `BooleanField(default=True)`
  - `can_view_financials`: `BooleanField(default=False)`
  - `can_submit_feedback`: `BooleanField(default=True)`
  - `is_active`: `BooleanField(default=True)`
  - `expires_at`: `DateTimeField(null=True, blank=True)`
  - `last_accessed_at`: `DateTimeField(null=True, blank=True, editable=False)`
  - `notes`: `TextField(blank=True)`
- Form (`forms/ClientExternalCollaboration/ClientPortals.py`):
  - `ClientPortalAccessForm(TenantModelForm)`:
    - `Meta.model = ClientPortalAccess`
    - `Meta.fields = ["project", "client_contact", "portal_user", "can_view_progress", "can_view_milestones", "can_view_deliverables", "can_view_financials", "can_submit_feedback", "is_active", "expires_at", "notes"]`
    - `_reject_foreign` checks `project`, `client_contact`, `portal_user`.

### 2.2 Entity 2: `ClientApprovalRequest` [`CFB-`] (`apps/projects/models/ClientExternalCollaboration/ClientFeedbacks.py`)
- Base: `TenantNumbered`, `NUMBER_PREFIX = "CFB"`
- Choices:
  - `STATUS_CHOICES = [("draft", "Draft"), ("pending_review", "Pending Review"), ("approved", "Approved"), ("rejected", "Rejected"), ("revision_requested", "Revision Requested")]`
- Fields:
  - `project`: `ForeignKey("projects.Project", on_delete=models.CASCADE, related_name="client_approval_requests")`
  - `deliverable_name`: `CharField(max_length=255)`
  - `document`: `ForeignKey("core.Document", on_delete=models.SET_NULL, null=True, blank=True, related_name="client_approval_requests")`
  - `milestone`: `ForeignKey("projects.ProjectMilestone", on_delete=models.SET_NULL, null=True, blank=True, related_name="client_approval_requests")`
  - `requested_by`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="requested_client_approvals")`
  - `assigned_contact`: `ForeignKey("core.Party", on_delete=models.SET_NULL, null=True, blank=True, related_name="assigned_client_approvals")`
  - `status`: `CharField(max_length=20, choices=STATUS_CHOICES, default="draft")`
  - `due_date`: `DateField(null=True, blank=True)`
  - `review_notes`: `TextField(blank=True)`
  - `client_feedback`: `TextField(blank=True)`
  - `signed_by_name`: `CharField(max_length=255, blank=True)`
  - `signed_at`: `DateTimeField(null=True, blank=True, editable=False)`
  - `rejection_reason`: `TextField(blank=True)`
- Form (`forms/ClientExternalCollaboration/ClientFeedbacks.py`):
  - `ClientApprovalRequestForm(TenantModelForm)`:
    - `Meta.model = ClientApprovalRequest`
    - `Meta.fields = ["project", "deliverable_name", "document", "milestone", "assigned_contact", "status", "due_date", "review_notes", "client_feedback"]`

### 2.3 Entity 3: `StatementOfWork` [`SOW-`] & `SOWAmendment` [`SWA-`] (`apps/projects/models/ClientExternalCollaboration/StatementOfWorks.py`)
- Base: `TenantNumbered`, `NUMBER_PREFIX = "SOW"`
- Choices:
  - `BILLING_TYPE_CHOICES = [("fixed_fee", "Fixed Fee"), ("time_and_materials", "Time & Materials"), ("milestone_based", "Milestone-Based"), ("retainer", "Retainer")]`
  - `STATUS_CHOICES = [("draft", "Draft"), ("under_review", "Under Review"), ("active", "Active"), ("amended", "Amended"), ("completed", "Completed"), ("terminated", "Terminated")]`
- Fields on `StatementOfWork`:
  - `project`: `ForeignKey("projects.Project", on_delete=models.CASCADE, related_name="statements_of_work")`
  - `client`: `ForeignKey("core.Party", on_delete=models.CASCADE, related_name="client_sows")`
  - `title`: `CharField(max_length=255)`
  - `sow_code`: `CharField(max_length=64, blank=True)`
  - `billing_type`: `CharField(max_length=25, choices=BILLING_TYPE_CHOICES, default="fixed_fee")`
  - `contract_value`: `DecimalField(max_digits=14, decimal_places=2, default=Decimal("0.00"), validators=[MinValueValidator(Decimal("0.00"))])`
  - `currency`: `ForeignKey("accounting.Currency", on_delete=models.PROTECT, null=True, blank=True, related_name="+")`
  - `start_date`: `DateField()`
  - `end_date`: `DateField()`
  - `status`: `CharField(max_length=20, choices=STATUS_CHOICES, default="draft")`
  - `scope_summary`: `TextField(blank=True)`
  - `terms_and_conditions`: `TextField(blank=True)`
  - `activated_at`: `DateTimeField(null=True, blank=True, editable=False)`
  - `activated_by`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, editable=False, related_name="+")`
- Fields on `SOWAmendment`:
  - `tenant`: `ForeignKey("core.Tenant", on_delete=models.CASCADE, related_name="+")`
  - `sow`: `ForeignKey(StatementOfWork, on_delete=models.CASCADE, related_name="amendments")`
  - `amendment_number`: `PositiveIntegerField(default=1)`
  - `title`: `CharField(max_length=255)`
  - `effective_date`: `DateField()`
  - `value_change`: `DecimalField(max_digits=14, decimal_places=2, default=Decimal("0.00"))`
  - `revised_scope`: `TextField(blank=True)`
  - `justification`: `TextField(blank=True)`
  - `status`: `CharField(max_length=15, choices=[("draft", "Draft"), ("approved", "Approved"), ("rejected", "Rejected")], default="draft")`
  - `approved_by`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, editable=False, related_name="+")`
  - `approved_at`: `DateTimeField(null=True, blank=True, editable=False)`
- Forms (`forms/ClientExternalCollaboration/StatementOfWorks.py`):
  - `StatementOfWorkForm(TenantModelForm)`
  - `SOWAmendmentForm(TenantModelForm)`

### 2.4 Entity 4: `VendorHandoff` [`VHD-`] (`apps/projects/models/ClientExternalCollaboration/VendorHandoffs.py`)
- Base: `TenantNumbered`, `NUMBER_PREFIX = "VHD"`
- Choices:
  - `STATUS_CHOICES = [("assigned", "Assigned"), ("in_progress", "In Progress"), ("delivered", "Delivered"), ("accepted", "Accepted"), ("rejected", "Rejected")]`
- Fields:
  - `project`: `ForeignKey("projects.Project", on_delete=models.CASCADE, related_name="vendor_handoffs")`
  - `vendor`: `ForeignKey("core.Party", on_delete=models.CASCADE, related_name="project_vendor_handoffs")`
  - `task`: `ForeignKey("projects.ProjectTask", on_delete=models.SET_NULL, null=True, blank=True, related_name="vendor_handoffs")`
  - `title`: `CharField(max_length=255)`
  - `description`: `TextField(blank=True)`
  - `handoff_date`: `DateField(default=timezone.localdate)`
  - `due_date`: `DateField(null=True, blank=True)`
  - `status`: `CharField(max_length=15, choices=STATUS_CHOICES, default="assigned")`
  - `deliverable_link`: `URLField(blank=True)`
  - `scorecard_rating`: `PositiveSmallIntegerField(null=True, blank=True, validators=[MinValueValidator(1), MaxValueValidator(5)])`
  - `performance_notes`: `TextField(blank=True)`
  - `accepted_at`: `DateTimeField(null=True, blank=True, editable=False)`
  - `accepted_by`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, editable=False, related_name="+")`
  - `deficiency_notes`: `TextField(blank=True)`
- Form (`forms/ClientExternalCollaboration/VendorHandoffs.py`):
  - `VendorHandoffForm(TenantModelForm)`

### 2.5 Entity 5: `ProjectClientInvoice` [`PCI-`] (`apps/projects/models/ClientExternalCollaboration/ClientInvoices.py`)
- Base: `TenantNumbered`, `NUMBER_PREFIX = "PCI"`
- Choices:
  - `BILLING_TYPE_CHOICES = [("fixed_fee", "Fixed Fee"), ("time_and_materials", "Time & Materials"), ("milestone", "Milestone-Based"), ("retainer", "Retainer")]`
  - `STATUS_CHOICES = [("draft", "Draft"), ("ready_to_bill", "Ready to Bill"), ("invoiced", "Invoiced"), ("cancelled", "Cancelled")]`
- Fields:
  - `project`: `ForeignKey("projects.Project", on_delete=models.CASCADE, related_name="client_invoices")`
  - `sow`: `ForeignKey(StatementOfWork, on_delete=models.SET_NULL, null=True, blank=True, related_name="billing_records")`
  - `milestone`: `ForeignKey("projects.ProjectMilestone", on_delete=models.SET_NULL, null=True, blank=True, related_name="billing_records")`
  - `billing_type`: `CharField(max_length=25, choices=BILLING_TYPE_CHOICES, default="milestone")`
  - `billing_date`: `DateField(default=timezone.localdate)`
  - `due_date`: `DateField(null=True, blank=True)`
  - `currency`: `ForeignKey("accounting.Currency", on_delete=models.PROTECT, null=True, blank=True, related_name="+")`
  - `amount`: `DecimalField(max_digits=14, decimal_places=2, default=Decimal("0.00"), validators=[MinValueValidator(Decimal("0.00"))])`
  - `tax_amount`: `DecimalField(max_digits=14, decimal_places=2, default=Decimal("0.00"), validators=[MinValueValidator(Decimal("0.00"))])`
  - `total_amount`: `DecimalField(max_digits=14, decimal_places=2, default=Decimal("0.00"), validators=[MinValueValidator(Decimal("0.00"))])`
  - `status`: `CharField(max_length=15, choices=STATUS_CHOICES, default="draft")`
  - `accounting_invoice`: `ForeignKey("accounting.Invoice", on_delete=models.SET_NULL, null=True, blank=True, related_name="project_billing_records")`
  - `invoiced_at`: `DateTimeField(null=True, blank=True, editable=False)`
  - `notes`: `TextField(blank=True)`
- Form (`forms/ClientExternalCollaboration/ClientInvoices.py`):
  - `ProjectClientInvoiceForm(TenantModelForm)`

---

## 3. URLs and View Context Variables Contract

| URL Name | Pattern | View Context Keys |
|---|---|---|
| `projects:cpa_list` | `client-portal-access/` | `access_list`, `projects`, `project_filter`, `status_filter` |
| `projects:cpa_create` | `client-portal-access/add/` | `form`, `is_edit=False` |
| `projects:cpa_detail` | `client-portal-access/<int:pk>/` | `access` |
| `projects:cpa_edit` | `client-portal-access/<int:pk>/edit/` | `form`, `is_edit=True`, `access` |
| `projects:cpa_delete` | `client-portal-access/<int:pk>/delete/` | POST only |
| `projects:cfb_list` | `client-approvals/` | `approval_list`, `projects`, `project_filter`, `status_choices`, `status_filter` |
| `projects:cfb_create` | `client-approvals/add/` | `form`, `is_edit=False` |
| `projects:cfb_detail` | `client-approvals/<int:pk>/` | `approval` |
| `projects:cfb_edit` | `client-approvals/<int:pk>/edit/` | `form`, `is_edit=True`, `approval` |
| `projects:cfb_delete` | `client-approvals/<int:pk>/delete/` | POST only |
| `projects:cfb_approve` | `client-approvals/<int:pk>/approve/` | POST only |
| `projects:cfb_reject` | `client-approvals/<int:pk>/reject/` | POST only |
| `projects:sow_list` | `statements-of-work/` | `sow_list`, `projects`, `project_filter`, `status_choices`, `status_filter` |
| `projects:sow_create` | `statements-of-work/add/` | `form`, `is_edit=False` |
| `projects:sow_detail` | `statements-of-work/<int:pk>/` | `sow`, `amendments` |
| `projects:sow_edit` | `statements-of-work/<int:pk>/edit/` | `form`, `is_edit=True`, `sow` |
| `projects:sow_delete` | `statements-of-work/<int:pk>/delete/` | POST only |
| `projects:sow_activate` | `statements-of-work/<int:pk>/activate/` | POST only |
| `projects:sow_amendment_create` | `statements-of-work/<int:pk>/amendments/add/` | `form`, `sow` |
| `projects:vhd_list` | `vendor-handoffs/` | `handoff_list`, `projects`, `project_filter`, `status_choices`, `status_filter` |
| `projects:vhd_create` | `vendor-handoffs/add/` | `form`, `is_edit=False` |
| `projects:vhd_detail` | `vendor-handoffs/<int:pk>/` | `handoff` |
| `projects:vhd_edit` | `vendor-handoffs/<int:pk>/edit/` | `form`, `is_edit=True`, `handoff` |
| `projects:vhd_delete` | `vendor-handoffs/<int:pk>/delete/` | POST only |
| `projects:vhd_accept` | `vendor-handoffs/<int:pk>/accept/` | POST only |
| `projects:vhd_reject` | `vendor-handoffs/<int:pk>/reject/` | POST only |
| `projects:pci_list` | `client-invoices/` | `invoice_list`, `projects`, `project_filter`, `status_choices`, `status_filter` |
| `projects:pci_create` | `client-invoices/add/` | `form`, `is_edit=False` |
| `projects:pci_detail` | `client-invoices/<int:pk>/` | `invoice_record` |
| `projects:pci_edit` | `client-invoices/<int:pk>/edit/` | `form`, `is_edit=True`, `invoice_record` |
| `projects:pci_delete` | `client-invoices/<int:pk>/delete/` | POST only |
| `projects:pci_generate_invoice` | `client-invoices/<int:pk>/generate-invoice/` | POST only |

---

## 4. Navigation Wire-up Contract (`apps/core/navigation.py`)

```python
"7.14": {
    "Client Portal & Visibility":       "projects:cpa_list",
    "Client Feedback & Approvals":      "projects:cfb_list",
    "Contract & SOW Management":        "projects:sow_list",
    "External Vendor Coordination":     "projects:vhd_list",
    "Billing & Invoicing to Clients":   "projects:pci_list",
    # Extra live leaves:
    "Statement of Work Register":       "projects:sow_list",
    "Vendor Coordination":              "projects:vhd_list",
    "Client Billing & Invoices":        "projects:pci_list",
}
```
