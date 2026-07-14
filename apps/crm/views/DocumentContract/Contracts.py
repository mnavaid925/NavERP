"""CRM 1.9 Document & Contract Management — Contracts views (split from apps/crm/views.py)."""
from apps.crm.views._common import *  # noqa: F401,F403
from apps.crm.models import (
    ContractDocument,
    DocumentVersion,
    Opportunity,
    SignerRecord,
)
from apps.crm.forms import (
    ContractDocumentForm,
    DocumentVersionForm,
    SignerRecordForm,
)


# ------------------------------------------------------------ 1.9 Contract documents
@login_required
def contractdocument_list(request):
    return crud_list(
        request,
        ContractDocument.objects.filter(tenant=request.tenant).select_related(
            "template", "opportunity", "account", "owner").defer("body_snapshot"),
        "crm/documents/contractdocument/list.html",
        search_fields=["number", "name", "account__name"],
        filters=[("status", "status", False), ("opportunity", "opportunity_id", True)],
        extra_context={"status_choices": ContractDocument.STATUS_CHOICES,
                       "opportunities": Opportunity.objects.filter(tenant=request.tenant).only("id", "number", "name").order_by("-created_at")[:200]},
    )


@login_required
def contractdocument_create(request):
    return crud_create(request, form_class=ContractDocumentForm,
                       template="crm/documents/contractdocument/form.html",
                       success_url="crm:contractdocument_list")


@login_required
def contractdocument_detail(request, pk):
    obj = get_object_or_404(
        ContractDocument.objects.select_related("template", "opportunity", "account", "owner"),
        pk=pk, tenant=request.tenant)
    return render(request, "crm/documents/contractdocument/detail.html", {
        "obj": obj,
        "signers": obj.signers.all(),  # signer_party isn't rendered — no JOIN needed (perf-review)
        "signer_form": SignerRecordForm(tenant=request.tenant),
        "versions": obj.versions.select_related("created_by").all(),
        "version_form": DocumentVersionForm(tenant=request.tenant),
    })


@login_required
def contractdocument_edit(request, pk):
    return crud_edit(request, model=ContractDocument, pk=pk, form_class=ContractDocumentForm,
                     template="crm/documents/contractdocument/form.html", success_url="crm:contractdocument_list")


@login_required
@require_POST
def contractdocument_delete(request, pk):
    return crud_delete(request, model=ContractDocument, pk=pk, success_url="crm:contractdocument_list")


@login_required
@require_POST
def contractdocument_add_signer(request, pk):
    contract = get_object_or_404(ContractDocument, pk=pk, tenant=request.tenant)
    form = SignerRecordForm(request.POST, tenant=request.tenant)
    if form.is_valid():
        signer = form.save(commit=False)
        signer.tenant = request.tenant
        signer.contract = contract
        signer.order = contract.signers.count() + 1  # append after existing signers
        signer.token = secrets.token_urlsafe(32)
        signer.save()
        write_audit_log(request.user, contract, "update",
                        {"action": "add_signer", "email": signer.signer_email})
        messages.success(request, "Signer added.")
    else:
        messages.error(request, "Could not add signer — name and email are required.")
    return redirect("crm:contractdocument_detail", pk=contract.pk)


@login_required
@require_POST
def contractdocument_remove_signer(request, pk, signer_pk):
    contract = get_object_or_404(ContractDocument, pk=pk, tenant=request.tenant)
    signer = get_object_or_404(SignerRecord, pk=signer_pk, contract=contract, tenant=request.tenant)
    signer.delete()
    messages.success(request, "Signer removed.")
    return redirect("crm:contractdocument_detail", pk=contract.pk)


def sign_document(request, token):
    """Public e-signature page (1.9) — token-scoped, no login. The 32-byte URL-safe
    token is the bearer credential; an unguessable token gates access to one signer row."""
    signer = get_object_or_404(SignerRecord.objects.select_related("contract"), token=token)
    contract = signer.contract
    # Refuse any action on an expired contract (legal/state-machine integrity).
    if contract.expires_at and contract.expires_at < timezone.now():
        if contract.status not in ("signed", "declined", "expired"):
            contract.status = "expired"
            contract.save(update_fields=["status", "updated_at"])
        return render(request, "crm/documents/sign_document.html",
                      {"signer": signer, "contract": contract, "already": True, "expired": True})
    already = signer.signed_at is not None or signer.declined_at is not None
    if request.method == "POST" and not already:
        with transaction.atomic():
            # Row-lock the signer to avoid a double-sign / lost-update race between two
            # concurrent last-signer POSTs (re-check state inside the lock).
            signer = (SignerRecord.objects.select_for_update()
                      .select_related("contract").get(pk=signer.pk))
            contract = signer.contract
            if signer.signed_at is None and signer.declined_at is None:
                signer.ip_address = request.META.get("REMOTE_ADDR")
                if request.POST.get("action") == "decline":
                    signer.declined_at = timezone.now()
                    signer.save(update_fields=["declined_at", "ip_address"])
                    contract.status = "declined"
                    contract.save(update_fields=["status", "updated_at"])
                else:
                    signer.signed_at = timezone.now()
                    signer.save(update_fields=["signed_at", "ip_address"])
                    if not contract.signers.filter(signed_at__isnull=True).exists():
                        contract.status = "signed"
                        contract.signed_at = timezone.now()
                        contract.save(update_fields=["status", "signed_at", "updated_at"])
                    elif contract.status in ("draft", "sent"):
                        contract.status = "viewed"
                        contract.save(update_fields=["status", "updated_at"])
        return redirect("crm:sign_document", token=token)
    if signer.viewed_at is None:
        signer.viewed_at = timezone.now()
        signer.save(update_fields=["viewed_at"])
    return render(request, "crm/documents/sign_document.html",
                  {"signer": signer, "contract": contract, "already": already})


# ---- 1.9 Document Generation + File Repository (version control) -------------------------
def _safe_doc_context(contract):
    """A string-only render context for DocTemplate bodies — NO model instances, so a user-authored
    template body can't traverse attributes or call methods (template-injection safe). Autoescape on."""
    acc, opp = contract.account, contract.opportunity
    return {
        "today": timezone.localdate().isoformat(),
        "contract": {"name": contract.name, "number": contract.number},
        "account": {"name": acc.name if acc else ""},
        "opportunity": {"name": opp.name if opp else "", "number": opp.number if opp else "",
                        "amount": str(opp.amount) if opp else ""},
        "owner": (contract.owner.get_full_name() or contract.owner.username) if contract.owner_id else "",
    }


# Isolated engine for rendering user-authored DocTemplate bodies. Its only builtins are RESTRICTED
# libraries carrying every Django default tag/filter EXCEPT the escape-bypass members (the
# ``safe``/``safeseq``/``json_script`` filters + the ``autoescape`` tag) and EXCEPT ``loader_tags``
# (so ``{% include %}``/``{% extends %}``/``{% load %}`` are invalid tags). A body can therefore only
# use ``{{ vars }}``, normal filters and ``{% if %}/{% for %}`` with auto-escaping ALWAYS on — it can
# never disable escaping, store raw markup, pull in internal templates, or load tag libs
# (security-review). Combined with the string-only ``_safe_doc_context`` (no model instances).
import django.template.defaultfilters as _doc_default_filters  # noqa: E402
import django.template.defaulttags as _doc_default_tags  # noqa: E402

_DOC_FILTER_LIB = Library()
for _fname, _ffn in _doc_default_filters.register.filters.items():
    if _fname not in {"safe", "safeseq", "json_script"}:
        _DOC_FILTER_LIB.filter(_fname, _ffn)
_DOC_TAG_LIB = Library()
for _tname, _tfn in _doc_default_tags.register.tags.items():
    if _tname != "autoescape":
        _DOC_TAG_LIB.tag(_tname, _tfn)


class _IsolatedDocEngine(Engine):
    default_builtins = []  # no auto builtins — restricted Library instances are injected directly below


_DOC_ENGINE = _IsolatedDocEngine(dirs=[], app_dirs=False, libraries={})
# Engine's ``builtins=`` / ``libraries=`` kwargs expect dotted import PATHS, not Library objects, so set
# the parsed builtins directly to our restricted libraries (no loader_tags / safe / safeseq / autoescape).
_DOC_ENGINE.template_builtins = [_DOC_TAG_LIB, _DOC_FILTER_LIB]


def _render_doc_body(contract):
    """Render a contract's linked template body against the safe context + isolated engine."""
    return _DOC_ENGINE.from_string(contract.template.body or "").render(Context(_safe_doc_context(contract)))


@login_required
@require_POST
def contractdocument_generate(request, pk):
    """1.9 Document Generation — render the linked template's merge variables into the contract body
    and capture it as a new immutable DocumentVersion. Rendered with a restricted string-only context
    + isolated engine so a template body can't reach model attributes/methods or include other files."""
    contract = get_object_or_404(
        ContractDocument.objects.select_related("template", "account", "opportunity", "owner"),
        pk=pk, tenant=request.tenant)  # the render reads all four FKs — avoid lazy per-FK queries
    if contract.status != "draft":
        messages.error(request, "Only a draft contract can be generated — its body is locked once sent.")
        return redirect("crm:contractdocument_detail", pk=pk)
    if contract.template_id is None:
        messages.error(request, "Link a document template first, then generate.")
        return redirect("crm:contractdocument_detail", pk=pk)
    try:
        rendered = _render_doc_body(contract)
    except Exception as e:  # a malformed template must not 500 the page  # noqa: BLE001
        messages.error(request, f"Template error: {e}")
        return redirect("crm:contractdocument_detail", pk=pk)
    with transaction.atomic():
        next_no = (contract.versions.aggregate(m=Max("version_no"))["m"] or 0) + 1
        contract.body_snapshot = rendered
        contract.current_version = next_no
        contract.save(update_fields=["body_snapshot", "current_version", "updated_at"])
        DocumentVersion.objects.create(
            tenant=request.tenant, contract=contract, version_no=next_no, body_snapshot=rendered,
            change_note=f"Generated from {contract.template.number}", created_by=request.user)
    write_audit_log(request.user, contract, "update", {"action": "generate", "version": next_no})
    messages.success(request, f"Generated v{next_no} from {contract.template.number}.")
    return redirect("crm:contractdocument_detail", pk=pk)


@login_required
@require_POST
def contractdocument_version_add(request, pk):
    """1.9 File Repository — capture a new revision: an uploaded file + the current body snapshot."""
    contract = get_object_or_404(ContractDocument, pk=pk, tenant=request.tenant)
    if contract.status in ("signed", "declined"):
        messages.error(request, "Can't add revisions to a signed or declined contract.")
        return redirect("crm:contractdocument_detail", pk=pk)
    form = DocumentVersionForm(request.POST, request.FILES, tenant=request.tenant)
    if form.is_valid():
        with transaction.atomic():
            next_no = (contract.versions.aggregate(m=Max("version_no"))["m"] or 0) + 1
            ver = form.save(commit=False)
            ver.tenant = request.tenant
            ver.contract = contract
            ver.version_no = next_no
            ver.body_snapshot = contract.body_snapshot
            ver.created_by = request.user
            ver.save()
            contract.current_version = next_no
            contract.save(update_fields=["current_version", "updated_at"])
        write_audit_log(request.user, contract, "update", {"action": "version_add", "version": next_no})
        messages.success(request, f"Revision v{next_no} added.")
    else:
        messages.error(request, "Could not add the revision — check the file type/size.")
    return redirect("crm:contractdocument_detail", pk=contract.pk)


@login_required
@require_POST
def contractdocument_send(request, pk):
    """1.9 — move a draft contract → sent (needs a generated body + at least one signer)."""
    contract = get_object_or_404(ContractDocument, pk=pk, tenant=request.tenant)
    if contract.status != "draft":
        messages.info(request, "Only a draft contract can be sent.")
        return redirect("crm:contractdocument_detail", pk=pk)
    if not contract.body_snapshot:
        messages.error(request, "Generate the document body before sending.")
        return redirect("crm:contractdocument_detail", pk=pk)
    if not contract.signers.exists():
        messages.error(request, "Add at least one signer before sending.")
        return redirect("crm:contractdocument_detail", pk=pk)
    contract.status = "sent"
    contract.save(update_fields=["status", "updated_at"])
    write_audit_log(request.user, contract, "update", {"action": "send"})
    messages.success(request, f"Contract {contract.number} marked as sent — share each signer's link.")
    return redirect("crm:contractdocument_detail", pk=pk)
