"""Procurement 6.13 Invoice & Voucher Management — SupplierInvoice views + the two boards.

Sixteen routes: the register (list/detail/create/edit/delete), the **Capture Invoice** two-stage
upload, the **Duplicate Invoice Detection** board, the match verbs (run / revalidate / override),
the privileged lifecycle transitions, and the **Invoice Dashboard**.

Discipline worth recording, because a reviewer will otherwise go looking for it:

* **Every queryset is ``filter(tenant=request.tenant)``** — never ``.all()``. Child rows (lines,
  variances, disputes) are reached through their header, which is itself tenant-scoped.
* **Ordinary CRUD is ``@login_required``; every privileged transition adds
  ``@tenant_admin_required`` and ``@require_POST``** (in that order) — approving, overriding,
  voiding and reversing are the moves that commit the workspace's money.
* **Every privileged verb runs under a row lock** (``select_for_update()`` inside
  ``transaction.atomic()``), so a double-submitted approval cannot mint a second bill: the model's
  ``if self.journal_entry_id: return False`` guard finds the entry already written and no-ops.
* **The templates are told what they may offer** through ``can_edit`` / ``can_match`` /
  ``can_override`` / ``can_approve`` / ``can_void`` / ``can_reverse``, each of which mirrors the
  decorator on the route it points at — a hidden button and a refused POST always agree.

The dashboard deliberately READS the other three lanes' tables (variances, disputes, lines). It is
the last lane to merge, so those imports are guaranteed to resolve by the time it renders; a
``NoReverseMatch`` on a tile URL would mean a lane is missing, which is a wiring bug worth seeing
rather than hiding behind a fallback link (the 6.12 ``_exception_rows`` precedent).
"""
import re
from collections import defaultdict
from datetime import datetime, timedelta
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Count, Q
from django.urls import reverse

from apps.core.crud import as_db_int, paginate
from apps.core.models import Document, Party
from apps.procurement.forms.InvoiceVoucherManagement.SupplierInvoices import (
    CaptureUploadForm, SupplierInvoiceForm, SupplierInvoiceLineFormSet)
from apps.procurement.models.InvoiceVoucherManagement.InvoiceDisputes import InvoiceDispute
# NOT-YET-WIRED entities of this SAME sub-module: import the entity MODULE directly, never
# ``from apps.procurement.models import X`` — the sub-package is not wired until the Integrator
# lands it and a package-level re-export is a star-import cycle at URLconf import.
from apps.procurement.models.InvoiceVoucherManagement.SupplierInvoices import SupplierInvoice
from apps.procurement.views._common import *  # noqa: F401,F403

ZERO = Decimal("0")

TEMPLATE_LIST = "procurement/invoicevouchermanagement/supplierinvoice/list.html"
TEMPLATE_DETAIL = "procurement/invoicevouchermanagement/supplierinvoice/detail.html"
TEMPLATE_FORM = "procurement/invoicevouchermanagement/supplierinvoice/form.html"
TEMPLATE_CAPTURE = "procurement/invoicevouchermanagement/capture.html"
TEMPLATE_DUPLICATES = "procurement/invoicevouchermanagement/duplicates.html"
TEMPLATE_DASHBOARD = "procurement/invoicevouchermanagement/dashboard.html"

#: How many recent invoices the duplicate board re-scans. The scan is a per-row duplicate lookup,
#: so it is capped rather than paginated at the database level — ``stats.scanned`` reports the cap
#: honestly so the tile can never claim to have looked at everything on a large workspace.
DUPLICATE_SCAN_LIMIT = 200

#: How far ahead the dashboard's "discount expiring" panel looks.
EXPIRING_WINDOW_DAYS = 7

#: Panels on the dashboard.
RECENT_LIMIT = 8
BLOCKED_LIMIT = 10
DISPUTE_LIMIT = 10

#: Dispute aging buckets, in the vocabulary ``InvoiceDispute.age_bucket`` returns.
AGING_BUCKETS = [
    ("overdue", "Overdue"),
    ("0-7", "0–7 days"),
    ("8-14", "8–14 days"),
    ("15-30", "15–30 days"),
    ("31-60", "31–60 days"),
    ("60+", "Over 60 days"),
    ("none", "No due date"),
]

#: Every status that is still live work — the complement of the terminal statuses.
OPEN_STATUSES = tuple(value for value, _label in SupplierInvoice.STATUS_CHOICES
                      if value not in SupplierInvoice.TERMINAL_STATUSES)

#: Every hop a row (or a row's own ``__str__``) walks on the register and the detail page.
#: ``goods_receipt`` belongs here, not on the detail tuple: the register row renders
#: ``obj.goods_receipt.number``, so omitting it was one extra query per GRN-bearing row — and the
#: same tuple is reused by the dashboard's recent/blocked panels and the duplicate board.
_ROW_RELATIONS = ("vendor", "purchase_order", "goods_receipt", "currency", "payment_term")

#: Every hop the detail page walks — it renders the whole document spine plus the ledger pointers.
_DETAIL_RELATIONS = _ROW_RELATIONS + (
    "tax_code", "document", "bill", "journal_entry", "approved_by",
    "duplicate_of", "source_submission", "tenant",
)


# -- shared helpers --------------------------------------------------------------------------

def _is_admin(request):
    """Mirrors ``@tenant_admin_required`` exactly, so a hidden button and a refused POST agree."""
    return bool(request.user.is_superuser or getattr(request.user, "is_tenant_admin", False))


def _need_tenant(request, what):
    """The superuser has no workspace by design; say so instead of rendering an empty page."""
    if request.tenant is None:
        messages.error(request, f"Select a tenant workspace to {what}.")
        return redirect("dashboard:home")
    return None


def _vendors(tenant):
    return Party.objects.filter(tenant=tenant).order_by("name")


def _invoice_stats(tenant):
    """The five list stat cards in ONE aggregate over the whole workspace.

    Counted over the WHOLE workspace, not the filtered page: a stat card answers "how much is
    outstanding?", which must not change because somebody typed a search.
    """
    return SupplierInvoice.objects.filter(tenant=tenant).aggregate(
        total=Count("id"),
        blocked=Count("id", filter=Q(status="blocked")),
        disputed=Count("id", filter=Q(status="disputed")),
        pending_approval=Count("id", filter=Q(status="pending_approval")),
        overdue=Count("id", filter=Q(due_date__lt=timezone.localdate(),
                                     status__in=OPEN_STATUSES)),
    )


def _tolerances():
    """The workspace's bands, mirrored into the detail page's ``tolerances`` panel.

    Read off the model class so a band can never be displayed as something other than the value
    ``run_match()`` actually applied.
    """
    return {
        "price_pct_upper": SupplierInvoice.PRICE_TOL_PCT_UPPER,
        "price_pct_lower": SupplierInvoice.PRICE_TOL_PCT_LOWER,
        "price_abs_upper": SupplierInvoice.PRICE_TOL_ABS_UPPER,
        "qty_pct_upper": SupplierInvoice.QTY_TOL_PCT_UPPER,
        "qty_abs_upper": SupplierInvoice.QTY_TOL_ABS_UPPER,
        "qty_pct_upper_no_grn": SupplierInvoice.QTY_TOL_PCT_UPPER_NO_GRN,
        "qty_pct_lower": SupplierInvoice.QTY_TOL_PCT_LOWER,
        "total_pct": SupplierInvoice.TOTAL_TOL_PCT,
        "total_abs": SupplierInvoice.TOTAL_TOL_ABS,
        "fx_pct": SupplierInvoice.FX_TOL_PCT,
        "tax_abs": SupplierInvoice.TAX_TOL_ABS,
        "duplicate_window_days": SupplierInvoice.DUPLICATE_WINDOW_DAYS,
        "duplicate_amount_tol_pct": SupplierInvoice.DUPLICATE_AMOUNT_TOL_PCT,
        "discount_annualisation_days": SupplierInvoice.DISCOUNT_ANNUALISATION_DAYS,
    }


def _discount_panel(obj):
    """The early-payment discount panel — what is on offer, and whether it is still takeable."""
    today = timezone.localdate()
    amount = obj.discount_amount()
    base = obj.subtotal if obj.discount_base == "net_of_tax" else obj.total
    days_to_discount = None
    if obj.discount_date:
        days_to_discount = (obj.discount_date - today).days
    expiry = obj.discount_expiry_date or obj.discount_date
    capturable = bool(amount > ZERO and expiry and expiry >= today)
    return {
        "base_amount": base,
        "amount": amount,
        "payable_if_discounted": obj.total - amount,
        "days_to_discount": days_to_discount,
        "annualised_pct": obj.annualised_pct(),
        "capturable": capturable,
    }


# -- the register ------------------------------------------------------------------------------

@login_required
def supplierinvoice_list(request):
    guard = _need_tenant(request, "review supplier invoices")
    if guard is not None:
        return guard
    return crud_list(
        request,
        SupplierInvoice.objects.filter(tenant=request.tenant).select_related(*_ROW_RELATIONS),
        TEMPLATE_LIST,
        search_fields=["number", "invoice_number", "invoice_number_norm", "external_ref",
                       "vendor__name"],
        # (get_param, orm_lookup, is_int) — the int one goes through crud_list's as_db_int guard,
        # so ?vendor=abc / ?vendor=999999999999999999999 skip the filter instead of 500ing (L11).
        filters=[("status", "status", False), ("match_status", "match_status", False),
                 ("vendor", "vendor_id", True), ("source", "source", False),
                 ("invoice_type", "invoice_type", False)],
        extra_context={
            "status_choices": SupplierInvoice.STATUS_CHOICES,
            "match_status_choices": SupplierInvoice.MATCH_STATUS_CHOICES,
            "source_choices": SupplierInvoice.SOURCE_CHOICES,
            "invoice_type_choices": SupplierInvoice.INVOICE_TYPE_CHOICES,
            "vendors": _vendors(request.tenant),
            "stats": _invoice_stats(request.tenant),
        },
    )


@login_required
def supplierinvoice_detail(request, pk):
    obj = get_object_or_404(
        SupplierInvoice.objects.select_related(*_DETAIL_RELATIONS), pk=pk, tenant=request.tenant)
    is_admin = _is_admin(request)
    return render(request, TEMPLATE_DETAIL, {
        "obj": obj,
        "lines": list(obj.lines.select_related("po_line", "receipt_line", "gl_account",
                                               "tax_code").order_by("id")),
        "variances": list(obj.variances.select_related("invoice_line", "dispute")
                          .order_by("-detected_at", "-id")),
        "disputes": list(obj.disputes.select_related("supplier", "assigned_to")
                         .order_by("-raised_at", "-id")),
        "bill": obj.bill,
        "journal_entry": obj.journal_entry,
        # Never auto-rejected: the panel shows the EVIDENCE, the linking decision is a person's.
        "duplicate_candidates": [{"invoice": candidate, "reasons": reasons}
                                 for candidate, reasons in obj.duplicate_candidates()],
        "discount": _discount_panel(obj),
        "allowed_transitions": list(SupplierInvoice.ALLOWED_TRANSITIONS.get(obj.status, ())),
        "is_locked": obj.is_locked,
        "tolerances": _tolerances(),
        # Each flag mirrors the decorator on the route it gates — the sidebar must never offer a
        # button that would 403.
        "can_edit": obj.status in SupplierInvoice.EDITABLE_STATUSES,
        # Exactly the statuses _submit() can carry to pending approval: draft/parked are captured
        # on the way through, captured/disputed go straight.
        "can_submit": obj.status in ("draft", "parked", "captured", "disputed"),
        "can_match": (not obj.is_locked and not obj.journal_entry_id
                      and obj.invoice_type != "credit_memo"),
        "can_override": is_admin and obj.status == "blocked",
        "can_approve": is_admin and obj.status == "pending_approval",
        # Mirrors void()'s own guard: a posted invoice is reversed, never voided.
        "can_void": is_admin and not obj.is_locked and not obj.journal_entry_id,
        "can_reverse": is_admin and obj.status in ("paid", "approved") and bool(obj.journal_entry_id),
        "is_admin": is_admin,
    })


def _invoice_form(request, instance=None):
    """Header + line formset in ONE transaction, then the header money re-derived.

    Hand-rolled rather than ``crud_create`` / ``crud_edit`` because it stamps the tenant on the
    header, saves the formset against the header it just wrote, and re-derives the money columns
    from the lines that survived.
    """
    is_edit = instance is not None
    if request.method == "POST":
        form = SupplierInvoiceForm(request.POST, request.FILES, instance=instance,
                                   tenant=request.tenant)
        line_formset = SupplierInvoiceLineFormSet(request.POST, instance=instance,
                                                  form_kwargs={"tenant": request.tenant})
        if form.is_valid() and line_formset.is_valid():
            with transaction.atomic():
                obj = form.save(commit=False)
                obj.tenant = request.tenant
                obj.save()
                line_formset.instance = obj
                line_formset.save()
                # The line formset has just changed the lines; the header money must follow them.
                obj.recalc_totals(save=True)
            write_audit_log(request.user, obj, "update" if is_edit else "create")
            messages.success(request, f"Supplier invoice {obj.number} saved.")
            return redirect("procurement:supplierinvoice_detail", pk=obj.pk)
    else:
        form = SupplierInvoiceForm(instance=instance, tenant=request.tenant)
        line_formset = SupplierInvoiceLineFormSet(instance=instance,
                                                  form_kwargs={"tenant": request.tenant})
    return render(request, TEMPLATE_FORM, {
        "form": form,
        "line_formset": line_formset,
        "obj": instance,
        "is_edit": is_edit,
        "title": "Edit supplier invoice" if is_edit else "New supplier invoice",
        "submit_label": "Save changes" if is_edit else "Create invoice",
        "cancel_url": (reverse("procurement:supplierinvoice_detail", args=[instance.pk]) if is_edit
                       else reverse("procurement:supplierinvoice_list")),
    })


@login_required
def supplierinvoice_create(request):
    guard = _need_tenant(request, "capture supplier invoices")
    if guard is not None:
        return guard
    return _invoice_form(request, instance=None)


@login_required
def supplierinvoice_edit(request, pk):
    obj = get_object_or_404(SupplierInvoice, pk=pk, tenant=request.tenant)
    if obj.status not in SupplierInvoice.EDITABLE_STATUSES:
        messages.error(
            request,
            f"{obj.number} is {obj.get_status_display().lower()} — only a draft, parked or "
            f"captured invoice can be edited.")
        return redirect("procurement:supplierinvoice_detail", pk=pk)
    return _invoice_form(request, instance=obj)


@login_required
@tenant_admin_required
@require_POST
def supplierinvoice_delete(request, pk):
    """Admin-gated: a deleted invoice takes its lines and variances with it, and the everyday way
    to withdraw one is ``void`` — which keeps the row and its reason.

    A POSTED invoice is refused outright. Its ``accounting.Bill`` and ``JournalEntry`` are not
    cascaded (they are the ledger's, not this module's), so deleting the header would leave those
    rows behind with no source document and take the lines, variances and disputes that explain
    them with it.
    """
    obj = get_object_or_404(SupplierInvoice, pk=pk, tenant=request.tenant)
    if obj.journal_entry_id or obj.status not in SupplierInvoice.EDITABLE_STATUSES:
        messages.error(
            request,
            f"{obj.number} is {obj.get_status_display().lower()} — void or reverse it instead of "
            f"deleting it.")
        return redirect("procurement:supplierinvoice_detail", pk=pk)
    return crud_delete(request, model=SupplierInvoice, pk=pk,
                       success_url="procurement:supplierinvoice_list")


# -- Capture Invoice -----------------------------------------------------------------------------
# The contract is explicit that the UI must never SAY "OCR": ``pdfplumber`` is imported LAZILY and
# is optional, so a deployment without it takes the designed fallback path —
# ``has_text_layer=False``, ``source="manual"``, ``extraction_confidence=0`` and an honest warning —
# and the page then renders the ordinary create form for hand-keying.

_DATE_RE = r"(\d{4}-\d{2}-\d{2}|\d{1,2}[/.-]\d{1,2}[/.-]\d{2,4})"
_AMOUNT_RE = r"([-+]?\d[\d,]*\.?\d*)"

#: ``field -> (anchor regex, value regex)``. The anchor is what makes a hit HIGH confidence; a bare
#: value-pattern hit is only MEDIUM, because "12,400.00" on an invoice page could be anything.
_EXTRACTION_PATTERNS = {
    "invoice_number": (r"invoice\s*(?:no|number|num|#)", r"[A-Z0-9][A-Z0-9\-/]{2,}"),
    "invoice_date": (r"invoice\s*date", _DATE_RE),
    "due_date": (r"due\s*date", _DATE_RE),
    "po_number": (r"(?:p\.?o\.?|purchase\s*order)\s*(?:no|number|#)?", r"[A-Z0-9][A-Z0-9\-/]{2,}"),
    "subtotal": (r"sub\s*-?\s*total", _AMOUNT_RE),
    "tax_total": (r"(?:tax|vat|gst)\s*(?:total|amount)?", _AMOUNT_RE),
    "total": (r"(?<!sub)(?<!sub-)\b(?:grand\s*)?total", _AMOUNT_RE),
    "currency_code": (r"currency", r"\b([A-Z]{3})\b"),
    "vendor_name": (r"(?:from|vendor|supplier|sold\s*by)", r"[A-Z][A-Za-z0-9 &.,'-]{2,60}"),
}

_DATE_FORMATS = ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%d.%m.%Y", "%m/%d/%Y")


def _empty_extraction():
    return {key: {"value": "", "confidence": "none"} for key in _EXTRACTION_PATTERNS}


def _extract_field(text, key):
    """``(value, confidence)`` for one header field — anchor hit is high, bare hit is medium."""
    anchor, pattern = _EXTRACTION_PATTERNS[key]
    labelled = re.search(anchor + r"\s*[:.]?\s*" + pattern, text, re.IGNORECASE)
    if labelled:
        return labelled.group(1).strip(), "high"
    bare = re.search(pattern, text)
    if bare:
        return bare.group(1).strip(), "medium"
    return "", "none"


def _extract_from_text(text):
    """The extraction dict plus an overall confidence score (0–100)."""
    extraction = {}
    score = Decimal("0")
    for key in _EXTRACTION_PATTERNS:
        value, confidence = _extract_field(text, key)
        extraction[key] = {"value": value, "confidence": confidence}
        if confidence == "high":
            score += Decimal("1")
        elif confidence == "medium":
            score += Decimal("0.5")
    total = Decimal(len(_EXTRACTION_PATTERNS))
    confidence = (score / total * Decimal("100")).quantize(Decimal("0.01"))
    return extraction, confidence


def _pdf_text(document):
    """``(raw_text, warnings)`` for an uploaded PDF — honest about what it could NOT do."""
    try:
        import pdfplumber
    except ImportError:
        pdfplumber = None

    if pdfplumber is None:
        return "", ["Automatic text extraction is not installed on this server — every field "
                    "below is empty and must be keyed by hand."]
    path = getattr(document.file, "path", None) if document is not None else None
    if not path:
        return "", ["The uploaded file could not be read back — key the invoice by hand."]
    try:
        with pdfplumber.open(path) as pdf:
            text = "\n".join((page.extract_text() or "") for page in pdf.pages)
    except Exception:                                    # malformed PDF — a page, not a 500
        return "", ["That PDF could not be read — key the invoice by hand."]
    if not (text or "").strip():
        return "", ["This PDF has no text layer (it looks like a scan) — every field below is "
                    "empty and must be keyed by hand."]
    return text, []


def _extraction_context(document):
    """Everything the capture page renders about one upload."""
    raw_text, warnings = _pdf_text(document)
    if raw_text.strip():
        extraction, confidence = _extract_from_text(raw_text)
        return {
            "extraction": extraction,
            "confidence": confidence,
            "source": "pdf_text_layer",
            "has_text_layer": True,
            "warnings": warnings,
            "raw_text": raw_text,
        }
    return {
        "extraction": _empty_extraction(),
        "confidence": ZERO,
        "source": "manual",
        "has_text_layer": False,
        "warnings": warnings,
        "raw_text": "",
    }


def _parse_date(raw):
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(raw, fmt).date()
        except (ValueError, TypeError):
            continue
    return None


def _capture_initial(extraction):
    """Prefill for the confirm-stage form — every extracted value stays EDITABLE."""
    initial = {}
    number = extraction["invoice_number"]["value"]
    if number:
        initial["invoice_number"] = number[:64]
    for key, field in (("invoice_date", "invoice_date"), ("due_date", "posting_date")):
        parsed = _parse_date(extraction[key]["value"])
        if parsed is not None:
            initial[field] = parsed
    return initial


def _capture_document(request):
    """The document the confirm stage is completing, re-validated against this workspace."""
    document_pk = as_db_int(request.POST.get("document", ""))
    if document_pk is None:
        return None
    return Document.objects.filter(pk=document_pk, tenant=request.tenant).first()


@login_required
def supplierinvoice_capture(request):
    """**Capture Invoice** — upload, review what could be read, key what could not.

    Two stages driven by a hidden ``stage`` field (``upload`` then ``confirm``). The file becomes a
    ``core.Document`` at stage one, so stage two only has to carry its pk — no re-upload, and no
    trusting a client-supplied filename.
    """
    guard = _need_tenant(request, "capture invoices")
    if guard is not None:
        return guard

    base = {"title": "Capture Invoice",
            "cancel_url": reverse("procurement:supplierinvoice_list")}

    if request.method == "POST":
        stage = (request.POST.get("stage") or "").strip()
        if stage == "upload":
            return _capture_upload(request, base)
        if stage == "confirm":
            return _capture_confirm(request, base)
        # A crafted stage value falls back to the upload card rather than 500ing.
        stage = "upload"
    else:
        stage = "upload"

    return render(request, TEMPLATE_CAPTURE, dict(base, **{
        "stage": stage,
        "upload_form": CaptureUploadForm(),
        "form": None,
        "document": None,
        "extraction": _empty_extraction(),
        "confidence": None,
        "source": "manual",
        "has_text_layer": False,
        "warnings": [],
        "raw_text": "",
    }))


def _capture_upload(request, base):
    upload_form = CaptureUploadForm(request.POST, request.FILES)
    if not upload_form.is_valid():
        return render(request, TEMPLATE_CAPTURE, dict(base, **{
            "stage": "upload", "upload_form": upload_form, "form": None, "document": None,
            "extraction": _empty_extraction(), "confidence": None, "source": "manual",
            "has_text_layer": False, "warnings": [], "raw_text": "",
        }))

    upload = upload_form.cleaned_data["document_file"]
    document = Document.objects.create(tenant=request.tenant, file=upload,
                                       name=(upload.name or "supplier invoice")[:255])
    context = _extraction_context(document)
    return render(request, TEMPLATE_CAPTURE, dict(base, **{
        "stage": "confirm",
        "upload_form": upload_form,
        "form": SupplierInvoiceForm(tenant=request.tenant,
                                    initial=_capture_initial(context["extraction"])),
        "document": document,
        **context,
    }))


def _capture_confirm(request, base):
    document = _capture_document(request)
    context = _extraction_context(document)

    # Capture is HEADER-ONLY by design: capture.html has no lines section, so a formset here would
    # be bound to a POST that carries no ManagementForm and could never validate — the confirm
    # stage would silently refuse to save. Lines are keyed on the invoice itself afterwards.
    form = SupplierInvoiceForm(request.POST, tenant=request.tenant)
    if form.is_valid():
        with transaction.atomic():
            obj = form.save(commit=False)
            obj.tenant = request.tenant
            obj.document = document
            # Capture provenance — system-set, never on the form.
            obj.source = context["source"]
            obj.extraction_confidence = context["confidence"]
            obj.extraction_raw_text = context["raw_text"]
            obj.save()
            obj.recalc_totals(save=True)
        write_audit_log(request.user, obj, "create",
                        {"action": "capture", "source": obj.source})
        messages.success(request, f"Supplier invoice {obj.number} captured.")
        return redirect("procurement:supplierinvoice_detail", pk=obj.pk)

    # Re-rendered with the extraction carried over, so nothing the reviewer already looked at has
    # to be uploaded twice just because a required field was missed.
    return render(request, TEMPLATE_CAPTURE, dict(base, **{
        "stage": "confirm", "upload_form": CaptureUploadForm(), "form": form,
        "document": document, **context,
    }))


# -- duplicate detection ---------------------------------------------------------------------------

@login_required
def supplierinvoice_duplicates(request):
    """**Duplicate Invoice Detection** — grouped suspicions, newest invoices first.

    Nothing here is a decision: the board reports, AP reviews, and linking an invoice as a
    duplicate is a separate, deliberate act (§8.1).
    """
    guard = _need_tenant(request, "review duplicate invoices")
    if guard is not None:
        return guard

    scanned = list(SupplierInvoice.objects.filter(tenant=request.tenant)
                   .select_related(*_ROW_RELATIONS)
                   .order_by("-invoice_date", "-id")[:DUPLICATE_SCAN_LIMIT])

    # TWO queries for the whole board, not 1 + DUPLICATE_SCAN_LIMIT: every peer that shares a
    # normalised number with anything on the scan is fetched once and bucketed here, then handed
    # to the scorer. An empty ``norms`` short-circuits in the ORM (``__in=[]`` never reaches SQL).
    norms = {invoice.invoice_number_norm for invoice in scanned if invoice.invoice_number_norm}
    by_norm = defaultdict(list)
    for peer in (SupplierInvoice.objects
                 .filter(tenant=request.tenant, invoice_number_norm__in=norms)
                 .select_related(*_ROW_RELATIONS)
                 .order_by("-invoice_date", "-id")):
        by_norm[peer.invoice_number_norm].append(peer)

    groups = []
    for invoice in scanned:
        candidates = [
            {"invoice": candidate, "reasons": reasons}
            for candidate, reasons in invoice.duplicate_candidates(
                candidates=by_norm.get(invoice.invoice_number_norm, ()))]
        if candidates:
            groups.append({"invoice": invoice, "candidates": candidates,
                           "count": len(candidates)})

    page_obj = paginate(request, groups)
    return render(request, TEMPLATE_DUPLICATES, {
        # ``groups`` is the PAGE's slice, not the whole list — the board rendered every group on
        # every page while the pager underneath it counted them all, so "Next" changed nothing.
        # (The stats below still describe the whole scan, which is what a stat card is for.)
        "groups": page_obj.object_list,
        "page_obj": page_obj,
        "window_days": SupplierInvoice.DUPLICATE_WINDOW_DAYS,
        "stats": {
            "scanned": len(scanned),
            "suspect": len(groups),
            "linked": SupplierInvoice.objects.filter(tenant=request.tenant,
                                                     duplicate_of__isnull=False).count(),
        },
    })


# -- match verbs ------------------------------------------------------------------------------------

@login_required
@require_POST
def supplierinvoice_match(request, pk):
    """Re-run the match. Under a row lock so two clicks cannot interleave their variance rows."""
    guard = _need_tenant(request, "match invoices")
    if guard is not None:
        return guard
    with transaction.atomic():
        obj = get_object_or_404(SupplierInvoice.objects.select_for_update(),
                                pk=pk, tenant=request.tenant)
        # A posted invoice must not be re-matched: run_match() would reset the status back to
        # pending_approval/blocked, after which approve() no-ops on its journal_entry_id guard and
        # reverse() is no longer offered — a GL-posted invoice stranded by a plain member.
        if obj.is_locked or obj.journal_entry_id:
            messages.error(request, f"{obj.number} is already posted — reverse it instead of "
                                    f"re-matching it.")
            return redirect("procurement:supplierinvoice_detail", pk=pk)
        _status, counts = obj.run_match(request.user)
    write_audit_log(request.user, obj, "update", {"action": "match"})
    messages.success(
        request,
        f"Match complete for {obj.number}: {counts['auto_accept']} within tolerance, "
        f"{counts['warn']} warning(s), {counts['block']} blocking.")
    return redirect("procurement:supplierinvoice_detail", pk=pk)


@login_required
@tenant_admin_required
@require_POST
def supplierinvoice_revalidate(request):
    """Re-match every blocked or captured invoice in one sweep — the way a workspace recovers
    after a tolerance constant or a receipt has been corrected."""
    guard = _need_tenant(request, "re-match invoices")
    if guard is not None:
        return guard
    totals = {"auto_accept": 0, "warn": 0, "block": 0}
    with transaction.atomic():
        rows = list(SupplierInvoice.objects
                    .filter(tenant=request.tenant, status__in=("blocked", "captured"))
                    .select_for_update().order_by("id"))
        for invoice in rows:
            _status, counts = invoice.run_match(request.user)
            for key in totals:
                totals[key] += counts.get(key, 0)
    messages.success(
        request,
        f"Re-matched {len(rows)} invoice(s): {totals['block']} blocking, {totals['warn']} "
        f"warning(s), {totals['auto_accept']} within tolerance.")
    return redirect("procurement:matchvariance_list")


# -- privileged transitions -------------------------------------------------------------------------

def _transition(request, pk, action, invoke, success, refuse):
    """One privileged verb: lock the row, call it, report and audit.

    ``invoke`` re-checks its own guard and returns a bool. A ``ValidationError`` (only
    ``approve`` raises one — a missing GL account) is a CONFIGURATION fault, not a refusal, so it
    is reported as an error and the whole posting rolls back.
    """
    guard = _need_tenant(request, "change supplier invoices")
    if guard is not None:
        return guard
    with transaction.atomic():
        obj = get_object_or_404(SupplierInvoice.objects.select_for_update(),
                                pk=pk, tenant=request.tenant)
        try:
            done = invoke(obj)
        except ValidationError as exc:
            messages.error(request, " ".join(exc.messages))
            return redirect("procurement:supplierinvoice_detail", pk=pk)
        if not done:
            messages.error(request, refuse(obj))
            return redirect("procurement:supplierinvoice_detail", pk=pk)
    write_audit_log(request.user, obj, "update", {"action": action})
    messages.success(request, success(obj))
    return redirect("procurement:supplierinvoice_detail", pk=pk)


def _refuse(obj, verb):
    return (f"{obj.number} is {obj.get_status_display().lower()} and cannot be {verb}.")


def _submit(obj):
    """Capture-then-submit, so one button carries a half-keyed invoice to the approver.

    ``submit_for_approval()`` only accepts ``captured`` or ``disputed``, and nothing else in the
    module calls ``capture()`` — which is why a CREDIT MEMO could never leave draft: ``run_match()``
    early-returns on one without touching its status, so the match verb (the ordinary route into
    ``pending_approval``) is a no-op for it and the credit never reached the ledger.
    """
    if obj.status in ("draft", "parked"):
        obj.capture()
    return obj.submit_for_approval()


@login_required
@require_POST
def supplierinvoice_submit(request, pk):
    """Send the invoice for approval — ordinary work, not an admin verb (approving it is)."""
    return _transition(
        request, pk, "submit",
        _submit,
        lambda obj: f"{obj.number} sent for approval.",
        lambda obj: _refuse(obj, "sent for approval"),
    )


@login_required
@tenant_admin_required
@require_POST
def supplierinvoice_approve(request, pk):
    """The ONLY route that writes the ledger."""
    return _transition(
        request, pk, "approve",
        lambda obj: obj.approve(request.user),
        lambda obj: (f"{obj.number} approved and posted — bill {obj.bill.number}, "
                     f"entry {obj.journal_entry.number}."),
        lambda obj: _refuse(obj, "approved"),
    )


@login_required
@tenant_admin_required
@require_POST
def supplierinvoice_override(request, pk):
    """Accept every blocking variance and move a blocked invoice on."""
    return _transition(
        request, pk, "override",
        lambda obj: obj.override(request.user),
        lambda obj: f"{obj.number} overridden — the blocking variances were accepted.",
        lambda obj: _refuse(obj, "overridden"),
    )


@login_required
@tenant_admin_required
@require_POST
def supplierinvoice_void(request, pk):
    reason = (request.POST.get("reason") or "").strip()
    return _transition(
        request, pk, "void",
        lambda obj: obj.void(request.user, reason),
        lambda obj: f"{obj.number} voided.",
        lambda obj: _refuse(obj, "voided"),
    )


@login_required
@tenant_admin_required
@require_POST
def supplierinvoice_reverse(request, pk):
    return _transition(
        request, pk, "reverse",
        lambda obj: obj.reverse(request.user),
        lambda obj: f"{obj.number} reversed — a mirroring journal entry was posted.",
        lambda obj: _refuse(obj, "reversed"),
    )


# -- payment scheduling --------------------------------------------------------------------------

@login_required
@require_POST
def supplierinvoice_schedule(request, pk):
    return _transition(
        request, pk, "schedule",
        lambda obj: obj.schedule(),
        lambda obj: f"{obj.number} scheduled for payment.",
        lambda obj: _refuse(obj, "scheduled"),
    )


@login_required
@tenant_admin_required
@require_POST
def supplierinvoice_mark_paid(request, pk):
    return _transition(
        request, pk, "mark_paid",
        lambda obj: obj.mark_paid(),
        lambda obj: f"{obj.number} marked as paid.",
        lambda obj: _refuse(obj, "marked as paid"),
    )


# -- the dashboard -----------------------------------------------------------------------------------

def _discount_qs(tenant):
    """Invoices still carrying a discount window in this workspace."""
    return (SupplierInvoice.objects.filter(tenant=tenant, status__in=OPEN_STATUSES)
            .exclude(discount_date=None).select_related(*_ROW_RELATIONS))


@login_required
def invoicevoucher_dashboard(request):
    """**Invoice Dashboard** — one page for the whole sub-module's health.

    Everything here is a COUNT or a bounded slice: a dashboard that issues an unbounded query per
    tile is the reason dashboards get switched off.
    """
    guard = _need_tenant(request, "use the invoice dashboard")
    if guard is not None:
        return guard

    tenant = request.tenant
    today = timezone.localdate()
    invoices = SupplierInvoice.objects.filter(tenant=tenant)

    status_counts = invoices.aggregate(
        invoices=Count("id"),
        blocked=Count("id", filter=Q(status="blocked")),
        disputed=Count("id", filter=Q(status="disputed")),
    )

    expiring_cutoff = today + timedelta(days=EXPIRING_WINDOW_DAYS)
    expiring, capturable_total = [], ZERO
    for invoice in _discount_qs(tenant).order_by("discount_date", "id"):
        panel = _discount_panel(invoice)
        if not panel["capturable"]:
            continue
        capturable_total += panel["amount"]
        if invoice.discount_date and invoice.discount_date <= expiring_cutoff:
            expiring.append({"invoice": invoice, "discount": panel})

    # ONE query feeds three consumers — the panel slice, the aging buckets and the open count.
    open_rows = list(InvoiceDispute.objects.filter(tenant=tenant,
                                                   status__in=InvoiceDispute.OPEN_STATUSES)
                     .select_related("supplier", "invoice")
                     .order_by("due_date", "-raised_at"))
    open_disputes = open_rows[:DISPUTE_LIMIT]
    aging = {key: 0 for key, _label in AGING_BUCKETS}
    for dispute in open_rows:
        bucket = dispute.age_bucket
        aging[bucket] = aging.get(bucket, 0) + 1

    tiles = [
        {"label": "Supplier invoices", "url": reverse("procurement:supplierinvoice_list"),
         "icon": "file-text", "count": status_counts["invoices"]},
        {"label": "Capture invoice", "url": reverse("procurement:supplierinvoice_capture"),
         "icon": "file-input", "count": None},
        {"label": "Match board", "url": reverse("procurement:invoice_match_board"),
         "icon": "git-merge", "count": None},
        {"label": "Match variances", "url": reverse("procurement:matchvariance_list"),
         "icon": "scale", "count": None},
        {"label": "Invoice lines", "url": reverse("procurement:supplierinvoiceline_list"),
         "icon": "layers", "count": None},
        {"label": "Duplicate suspects", "url": reverse("procurement:supplierinvoice_duplicates"),
         "icon": "copy", "count": None},
        {"label": "Payment schedule", "url": reverse("procurement:paymentschedule_list"),
         "icon": "calendar-clock", "count": None},
        {"label": "Invoice disputes", "url": reverse("procurement:invoicedispute_list"),
         "icon": "message-square-warning", "count": len(open_disputes)},
        {"label": "Dispute aging", "url": reverse("procurement:invoicedispute_aging"),
         "icon": "clock", "count": None},
    ]

    return render(request, TEMPLATE_DASHBOARD, {
        "tiles": tiles,
        "stats": {
            "invoices": status_counts["invoices"],
            "blocked": status_counts["blocked"],
            "disputed": status_counts["disputed"],
            "capturable_discount": capturable_total,
            "open_disputes": len(open_rows),
        },
        "recent": list(invoices.select_related(*_ROW_RELATIONS)
                       .order_by("-invoice_date", "-id")[:RECENT_LIMIT]),
        "blocked": list(invoices.filter(status="blocked").select_related(*_ROW_RELATIONS)
                        .order_by("-invoice_date", "-id")[:BLOCKED_LIMIT]),
        "expiring": expiring,
        "open_disputes": open_disputes,
        "aging": aging,
    })
