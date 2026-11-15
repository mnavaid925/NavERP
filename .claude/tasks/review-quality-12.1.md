# Review Findings — Module 12.1: Document Control & Management

**BASE:** `239c9345ff46a91dafa5d91940b3f5919b2d5814`  
**HEAD:** `583a618f464ab5ccb320c8b8193a5c10fc9b6420`

---

## Review Pass 1 — `code-reviewer`

### Critical
- [ ] **CR-C1**: `apps/quality/views/DocumentControl/DocumentAcknowledgments.py:165` & `templates/quality/documentcontrol/document_acknowledgment/list.html:163` — Missing user assignment check in `document_acknowledgment_sign` allows any authenticated user to sign an acknowledgment requirement assigned to someone else. Fix: verify `if request.user != ack.user and not (request.user.is_superuser or getattr(request.user, "is_tenant_admin", False)):` and reject with error message and redirect; also guard "Sign" button in `list.html`.

### Important
- [ ] **CR-I1**: `apps/quality/views/DocumentControl/DocumentChangeOrders.py:195` — `document_change_order_ccb_decision` lacks a view-level status guard, allowing CCB determinations on change orders that are already implemented, rejected, or in draft. Fix: add `if dco.status not in {"submitted", "in_assessment", "ccb_review"}:` check and redirect with error message.
- [ ] **CR-I2**: `templates/quality/documentcontrol/document_change_order/detail.html:152` — Unhandled nullable ForeignKey in template filter argument `default:change_order.ccb_decision_by.username` raises `VariableDoesNotExist` (HTTP 500) if `ccb_decision_date` is set but `ccb_decision_by` is None (Lesson L10). Fix: wrap in `{% if change_order.ccb_decision_by %}{{ change_order.ccb_decision_by.get_full_name|default:change_order.ccb_decision_by.username }}{% else %}—{% endif %}`.
- [ ] **CR-I3**: `apps/quality/views/DocumentControl/ControlledDocuments.py:143` & `apps/quality/views/DocumentControl/DocumentChangeOrders.py:122` — Detail views calculate `can_approve`, `can_make_effective`, `can_obsolete`, and `can_ccb_approve` without checking tenant admin status, presenting non-admin users with buttons that yield HTTP 403. Fix: gate each context boolean with `is_admin = request.user.is_superuser or getattr(request.user, "is_tenant_admin", False)`.
- [ ] **CR-I4**: `templates/quality/documentcontrol/controlled_document/detail.html:38`, `templates/quality/documentcontrol/document_change_order/detail.html:33`, `templates/quality/documentcontrol/document_acknowledgment/detail.html:27` — All three detail templates omit the status-conditional POST-only Delete action required by the NavERP CRUD contract. Fix: add `<form method="post" action="{% url ... %}">` delete button with CSRF token and confirm dialog to each detail actions header/sidebar.
- [ ] **CR-I5**: `apps/quality/views/DocumentControl/ElectronicSignatures.py:96` — `controlled_document_sign` lacks a lifecycle guard, allowing 21 CFR Part 11 signatures to be executed against locked, superseded, or obsolete documents. Fix: add `if doc.is_locked:` guard rejecting signature execution.

### Minor
- [ ] **CR-M1**: `apps/quality/views/DocumentControl/ControlledDocuments.py:136` — Revision history is queried by string `title=doc.title` rather than the model's explicit `supersedes` / `superseded_by` lineage ForeignKeys. Fix: traverse predecessor/successor relationships or key off an immutable family identifier.
- [ ] **CR-M2**: `apps/quality/management/commands/seed_quality.py:54` — Unordered `.first()` queries across `User`, `OrgUnit`, and `EmployeeProfile` introduce non-deterministic seeding across runs (Lesson L61). Fix: add `.order_by("pk")` to all `.first()` calls.
- [ ] **CR-M3**: `apps/quality/management/commands/seed_quality.py:45` — Seeder completion output omits the required reminder that the global `admin` superuser has `tenant=None` and cannot view seeded tenant records. Fix: print standard tenant admin login instructions and superuser warning.
- [ ] **CR-M4**: `apps/quality/forms/DocumentControl/ElectronicSignatures.py:35` — `ElectronicSignatureForm.clean_password` silently bypasses validation if `self.user` is None. Fix: enforce `if not self.user or not self.user.check_password(password): raise forms.ValidationError(...)`.
- [ ] **CR-M5**: `apps/quality/views/DocumentControl/ControlledDocuments.py:59` & `templates/quality/documentcontrol/controlled_document/list.html:82` — Filter `latest` defaults to `"1"` in the view but has no UI dropdown in the template and is omitted from pagination links. Fix: add a Revisions select filter and include `&latest={{ request.GET.latest }}` in pagination URLs.
- [ ] **CR-M6**: `templates/quality/documentcontrol/document_acknowledgment/list.html:148` — Status badge `{% else %}` renders a hardcoded "Pending Sign-Off" string instead of dynamic `{{ ack.get_status_display }}` fallback. Fix: use `{{ ack.get_status_display }}` in the fallback branch.

---

## Review Pass 2 — `explorer`

### Critical
None.

### Important
- [ ] **EX-I1**: `templates/quality/documentcontrol/controlled_document/detail.html:39-86` & `apps/quality/views/DocumentControl/ControlledDocuments.py:147,161` — Missing "Sign Document" action button in controlled document detail view. The view passes `can_sign=True` and the route exists, but the detail page actions omit the button to invoke `controlled_document_sign`. Fix: add a "Sign Document" button in detail actions guarded by `{% if can_sign %}`.
- [ ] **EX-I2**: `templates/quality/documentcontrol/document_change_order/detail.html:125-218` & `apps/quality/views/DocumentControl/DocumentChangeOrders.py:118,127` — Context variable `signatures` is queried and passed in `document_change_order_detail` but never rendered in the template. Fix: add a signature manifest table or section displaying linked change order electronic signatures.

### Minor
- [ ] **EX-M1**: `templates/quality/documentcontrol/document_change_order/list.html:79-110` & `apps/quality/views/DocumentControl/DocumentChangeOrders.py:50-53,75` — Filter `change_type` is supported by the view and `change_type_choices` is passed in context, but the `<select name="change_type">` dropdown is omitted from the template filter bar. Fix: add the change type select dropdown.
- [ ] **EX-M2**: `apps/quality/views/DocumentControl/DocumentAcknowledgments.py:205-209` & `templates/quality/documentcontrol/electronic_signature/form.html:13,21,85` — `document_acknowledgment_sign` view omits `"acknowledgment": ack` in context, causing breadcrumbs and Cancel to navigate to document detail instead of acknowledgment detail. Fix: pass `acknowledgment` in context and use conditional target in template.
- [ ] **EX-M3**: `.claude/tasks/contract-quality-12.1.md:16` — Contract listed `e_signature_modal.html` as placeholder, but implementation cleanly used dedicated `electronic_signature/form.html` page route. Fix: update contract note.

---

## Review Pass 3 — `frontend-reviewer`

### Critical
- [ ] **FR-C1**: `templates/quality/documentcontrol/document_change_order/detail.html:152` — Unhandled nullable ForeignKey in template filter argument `default:change_order.ccb_decision_by.username` raises `VariableDoesNotExist` (HTTP 500) if `ccb_decision_date` is set but `ccb_decision_by` is None. (Duplicate of CR-I2).

### Important
- [ ] **FR-I1**: `templates/quality/documentcontrol/document_change_order/detail.html:181` & `templates/quality/documentcontrol/electronic_signature/form.html:88` — HTML validity: `onsubmit` attribute placed on `<button>` elements instead of `<form>` elements (`onsubmit` is only valid on `<form>`). Fix: move `onsubmit` handler to the `<form>` element.
- [ ] **FR-I2**: `templates/quality/documentcontrol/controlled_document/detail.html:39-86` — "Sign Document" button missing from action buttons header. (Duplicate of EX-I1).
- [ ] **FR-I3**: `templates/quality/documentcontrol/controlled_document/detail.html:38`, `templates/quality/documentcontrol/document_change_order/detail.html:33`, `templates/quality/documentcontrol/document_acknowledgment/detail.html:27` — Missing POST delete action buttons. (Duplicate of CR-I4).

### Minor
- [ ] **FR-M1**: `templates/quality/documentcontrol/electronic_signature/detail.html:82-87` — Invalid markup: `<dt>` and `<dd>` tags used outside of a parent `<dl>` list. Fix: wrap with `<dl>` or convert to `<div>` layout.
- [ ] **FR-M2**: `templates/quality/documentcontrol/vault/document_archive_vault.html:70` — Missing accessible `<label>` or `aria-label` for vault search input. Fix: add `aria-label="Search vault archives"`.
- [ ] **FR-M3**: `templates/quality/documentcontrol/*/list.html` — Icon-only action links missing `aria-label` or `.sr-only` text for screen readers. Fix: add explicit `aria-label` attributes to table action links.

---

## Review Pass 4 — `performance-reviewer`

### Critical
None.

### Important
- [ ] **PR-I1**: `apps/quality/forms/DocumentControl/DocumentAcknowledgments.py:37` — N+1 query loop on `DocumentAcknowledgmentForm` via `EmployeeProfile.__str__`. When rendering the employee `<select>`, accessing `party.name` triggers N+1 queries without `select_related("party")`. Fix: add `.select_related("party")` to employee queryset in `DocumentAcknowledgmentForm.__init__`.
- [ ] **PR-I2**: `apps/quality/views/DocumentControl/DocumentChangeOrders.py:111-116`, `DocumentAcknowledgments.py:102-108`, `ElectronicSignatures.py:76-82` — Missing nested `select_related` on target document foreign keys in detail views (`document__department`, `document__owner`). Fix: expand `select_related` lists to include `document__department` and `document__owner`.
- [ ] **PR-I3**: `apps/quality/views/DocumentControl/ControlledDocuments.py:66-74,383-388`, `DocumentChangeOrders.py:54-60`, `DocumentAcknowledgments.py:51-56`, `ElectronicSignatures.py:49-56` — Multiple redundant `COUNT(*)` queries for KPI stat cards (4 to 5 count queries per view). Fix: consolidate into single `.aggregate(Count("id", filter=Q(...)))` per view.
- [ ] **PR-I4**: `apps/quality/models/DocumentControl/ElectronicSignatures.py:43` & `DocumentChangeOrders.py:70-71` — Missing database indexes on high-frequency filter and aggregation columns (`signature_meaning`, `change_type`, `priority`). Fix: add `models.Index` in `Meta.indexes`.

### Minor
- [ ] **PR-M1**: `apps/quality/views/DocumentControl/*.py` — CSV export views load full querysets into memory directly instead of batch streaming. Fix: use `qs.iterator(chunk_size=1000)` in export views.

---

## Review Pass 5 — `qa-smoke-tester`

### Critical
- [ ] **QA-C1**: `templates/quality/documentcontrol/document_change_order/detail.html:152` — Unhandled nullable ForeignKey in template filter argument `default:change_order.ccb_decision_by.username` raises `django.template.base.VariableDoesNotExist` (`Failed lookup for key [username] in None`), crashing the page with HTTP 500 when `ccb_decision_date` is set without an assigned user (Lesson L10). (Duplicate of CR-I2 / FR-C1).
- [ ] **QA-C2**: `apps/quality/views/DocumentControl/DocumentAcknowledgments.py:165` & `templates/quality/documentcontrol/document_acknowledgment/list.html:163` — Missing user authorization check in `document_acknowledgment_sign`. Verified via smoke test: unauthorized user successfully posted and executed a binding electronic signature for an acknowledgment assigned to another user. (Duplicate of CR-C1).

### Important
- [ ] **QA-I1**: `apps/quality/views/DocumentControl/DocumentChangeOrders.py:195` — Missing status check in `document_change_order_ccb_decision`. Verified via smoke test: a POST to `ccb-decision` directly approved a draft change order, bypassing submission and review. (Duplicate of CR-I1).
- [ ] **QA-I2**: `apps/quality/forms/DocumentControl/ElectronicSignatures.py:35` — `ElectronicSignatureForm.clean_password` silently skips credential verification if `self.user` is `None`, bypassing 21 CFR Part 11 authentication. (Duplicate of CR-M4).
- [ ] **QA-I3**: `apps/quality/views/DocumentControl/ElectronicSignatures.py:96` — `controlled_document_sign` lacks a lifecycle state guard, returning HTTP 200 and rendering the signature form even for locked, superseded, or obsolete documents. (Duplicate of CR-I5).
- [ ] **QA-I4**: `templates/quality/documentcontrol/controlled_document/detail.html:39-86` & `apps/quality/views/DocumentControl/ControlledDocuments.py:147` — View calculates and passes `can_sign=True` and route exists, but the detail actions bar omits the "Sign Document" button entirely. (Duplicate of EX-I1 / FR-I2).
- [ ] **QA-I5**: `apps/quality/views/DocumentControl/ControlledDocuments.py:143` & `apps/quality/views/DocumentControl/DocumentChangeOrders.py:122` — Detail views set `can_approve`, `can_make_effective`, `can_obsolete`, and `can_ccb_approve` based strictly on entity status without checking tenant admin permissions. (Duplicate of CR-I3).
- [ ] **QA-I6**: `templates/quality/documentcontrol/controlled_document/detail.html:38`, `templates/quality/documentcontrol/document_change_order/detail.html:33`, `templates/quality/documentcontrol/document_acknowledgment/detail.html:27` — Missing POST-only Delete action forms on all three detail templates. (Duplicate of CR-I4 / FR-I3).

### Minor
- [ ] **QA-M1**: `templates/quality/documentcontrol/document_change_order/list.html:79` & `apps/quality/views/DocumentControl/DocumentChangeOrders.py:50` — Filter `change_type` is implemented in the view and passed in context, but template filter bar omits `<select name="change_type">`. (Duplicate of EX-M1).
- [ ] **QA-M2**: `templates/quality/documentcontrol/controlled_document/list.html:82` & `apps/quality/views/DocumentControl/ControlledDocuments.py:59` — Filter `latest` defaults to `"1"` in the view but has no select dropdown in the list template and is not persisted across pagination links. (Duplicate of CR-M5).
- [ ] **QA-M3**: `apps/quality/views/DocumentControl/DocumentAcknowledgments.py:205` & `templates/quality/documentcontrol/electronic_signature/form.html:13,21,85` — View fails to pass `"acknowledgment": ack` in context, causing Cancel and breadcrumbs in `electronic_signature/form.html` to target document detail instead of acknowledgment detail. (Duplicate of EX-M2).
- [ ] **QA-M4**: `templates/quality/documentcontrol/electronic_signature/form.html:88` — Invalid HTML markup: `onsubmit` placed on `<button>` element instead of parent `<form>` element. (Duplicate of FR-I1).
- [ ] **QA-M5**: `templates/quality/documentcontrol/electronic_signature/detail.html:83-86` — Invalid HTML markup: `<dt>` and `<dd>` used inside a `<div>` without a parent `<dl>` list. (Duplicate of FR-M1).
