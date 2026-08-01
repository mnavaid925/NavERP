"""SCM 4.12 Contract & Compliance — ``TradeDocument`` views: raise, issue, file, void, print.

**Nothing here posts a StockMove and nothing here posts a JournalEntry** (L29). 4.12 is read-only
over 4.1-4.11: the only rows these views write are the document, its lines, and the two cached
counters on the ``TradeLicense`` the document is charged to.

**The verbs are where the module's one real invariant lives.** ``status`` is off the form precisely
so that issuing — the act that spends a licence balance — cannot happen by typing a word into a
dropdown. Each verb therefore follows the same lock-apply-audit shape as 4.9/4.10's actions:
``@require_POST``, then ``transaction.atomic()`` with the row re-read under ``select_for_update()``
INSIDE the transaction, then the guard, then a narrow ``save(update_fields=…)``, then
``write_audit_log``, then the message. The licence is locked SECOND and always second — one
direction for every route in this file, so two concurrent issues against one licence serialise
instead of deadlocking.

**Refuse, never clamp.** ``TradeLicense.can_charge()`` returns ``(allowed, reason)`` and
:func:`tradedocument_issue` shows the reason and stops. Charging what fits and letting the rest go
out unauthorised is precisely the failure a licence balance exists to prevent.

**Why the balance is re-derived rather than incremented.** Every route that changes whether this
document counts against its licence (issue, void, delete) calls ``license.recompute_usage()``, which
re-reads both figures from the documents themselves. ``+=`` on a cached counter is how a balance
drifts permanently; a re-derivation is always correct and is the model's stated invalidation path.
``submit`` and ``accept`` deliberately do NOT call it — ``issued``, ``submitted`` and ``accepted``
are all in ``CHARGING_STATUSES``, so moving between them changes no balance and writing the counters
again would only add a pointless UPDATE.

Context-var contract (pinned, L7 — the templates are written by a separate agent, so every key each
view supplies is listed here, not just the list variable):

* ``scm/compliance/tradedocument/list.html`` — ``object_list`` + ``page_obj`` + ``q`` (from
  ``crud_list``) plus ``status_choices``, ``doctype_choices``, ``direction_choices``, ``shipments``,
  ``licenses``.
* ``scm/compliance/tradedocument/form.html`` — ``form``, ``formset``, ``is_edit``, ``obj``
  (``None`` on create).
* ``scm/compliance/tradedocument/detail.html`` — ``obj``, ``lines``, ``has_lines``, ``lines_total``,
  ``value_matches``, ``charge_value``, ``charge_quantity``, ``license_warning``, ``can_edit``,
  ``can_issue``, ``can_submit``, ``can_accept``, ``can_void``.
* ``scm/compliance/tradedocument/print.html`` — ``obj``, ``lines``, ``lines_total``, ``printed_at``.

POST payloads the verb routes read. They take no ``Form``, so the template names these inputs:

* ``<int:pk>/submit/`` — OPTIONAL ``filing_reference`` (the AES/ITN or broker reference). Left blank
  it changes nothing. It is collected HERE because ``is_editable`` is draft/amended only, so once a
  document is issued the edit form can no longer reach the field — and submission is exactly when
  the reference comes back. 4.12 stores it; 4.12 does not file.
* ``<int:pk>/void/`` — REQUIRED ``reason`` (accepted as ``void_reason`` too). Voiding releases a
  licence balance, so the record of why is not optional.

``tradedocument_delete`` and ``tradedocument_void`` are ``@tenant_admin_required``. The template
hides their buttons with the house idiom ``{% if request.user.is_superuser or
request.user.is_tenant_admin %}`` — there is no context key for it, and offering a member a
one-click 403 is worse than not offering the button at all (the 4.11 finding).
"""
from apps.scm.views._common import *  # noqa: F401,F403
from apps.scm.views._common import _changed
from apps.scm.views._helpers import _need_tenant

from apps.scm.forms import TradeDocumentForm, TradeDocumentLineFormSet
# The clamped quantizers every computed Decimal in the app goes through: a POSTed figure can exceed
# what DecimalField(14, 2) / (14, 4) holds, and an over-range value raises DataError from inside the
# driver rather than failing validation. Both also turn an empty Sum -> None into a clean zero.
from apps.scm.models._base import q2, q4
from apps.scm.models import Shipment, TradeDocument, TradeLicense

#: Which status each verb may move FROM. Declared once so the guard inside the transaction, the
#: ``can_*`` flags the detail page renders its buttons from, and the refusal message can never
#: disagree about when an action is available (§7.5 — a gate lives in the view as well as on the
#: button). ``issue`` reads ``TradeDocument.EDITABLE_STATUSES`` rather than restating draft/amended,
#: because "may still be edited" and "may still be issued" are the same fact on this model.
_ISSUE_FROM = TradeDocument.EDITABLE_STATUSES
_SUBMIT_FROM = ("issued",)
_ACCEPT_FROM = ("submitted",)


def _document_queryset(tenant):
    """The detail/print base queryset — every FK a page renders, joined once.

    ``carrier__party`` because ``Carrier.__str__`` renders ``Carrier.name``, a property reading
    ``self.party.name``; ``purchase_order__vendor`` / ``sales_order__customer`` for the same reason
    on those two ``__str__``s. Joining the carrier alone would still cost a query per render.
    """
    return (TradeDocument.objects.filter(tenant=tenant)
            .select_related("shipment", "carrier__party", "purchase_order__vendor",
                            "sales_order__customer", "license", "shipper_party", "consignee_party",
                            "notify_party", "currency", "document", "issued_by"))


def _charge_figures(document):
    """``(value, quantity)`` this document draws from its licence.

    The SAME two grains ``TradeLicense.recompute_usage()`` sums, and computed in one place so the
    figure the detail page previews, the figure ``can_charge()`` is tested against and the figure the
    re-derivation actually stores cannot diverge. Value comes off the document (``declared_value``
    is what the filer declared) and quantity off its lines — asking for both in one ``aggregate()``
    would fan the document row out per line and multiply the value by the line count.
    """
    return q2(document.declared_value), q4(document.lines.aggregate(total=Sum("quantity"))["total"])


def _audit_value(value):
    """One side of a diff entry, JSON-safe. ``AuditLog.changes`` is a ``JSONField`` and a ``Decimal``
    / ``date`` / model instance is not serializable by the default encoder."""
    return None if value is None else str(value)[:200]


def _apply(obj, **changes):
    """Set only what actually MOVES, and return the ``{field: [before, after]}`` diff.

    An empty diff means the verb was a no-op — the callers below then flash ``messages.info`` and
    write NO audit row, because an audit trail of "nothing happened" is noise in the one log that
    has to stay readable.
    """
    diff = {}
    for field, after in changes.items():
        before = getattr(obj, field, None)
        if before == after:
            continue
        setattr(obj, field, after)
        diff[field] = [_audit_value(before), _audit_value(after)]
    return diff


def _locked_license(document, tenant):
    """The document's licence, re-read under ``SELECT … FOR UPDATE``, or ``None``.

    Locked SEPARATELY rather than through ``select_for_update().select_related("license")``: the FK
    is nullable, so that join is an OUTER one and PostgreSQL refuses ``FOR UPDATE`` against the
    nullable side of it. Two statements in a fixed order (document, then licence) lock exactly the
    two rows that matter and keep the ordering identical across every route in this file.
    """
    if document.license_id is None:
        return None
    return (TradeLicense.objects.select_for_update()
            .filter(pk=document.license_id, tenant=tenant).first())


# ==================================================================== the register
@login_required
def tradedocument_list(request):
    """Search + five filters over the tenant's paperwork.

    Every filter is applied BEFORE ``crud_list`` paginates — a filter applied after pagination pages
    over the unfiltered set and quietly shows the wrong rows on page 2. The two FK filters go
    through ``crud_list``'s ``filters`` spec, which is where the L11 guard lives: ``?shipment=abc``,
    ``?shipment=²`` and a 21-digit ``?shipment=…`` must all SKIP the filter rather than raise out of
    ``.filter()``.

    ``shipments`` offers only consignments that actually carry paperwork. The unfiltered alternative
    is the whole shipment table — thousands of ``<option>``s of which all but a handful select
    nothing — so this is both the bounded query and the more useful dropdown.
    """
    qs = (TradeDocument.objects.filter(tenant=request.tenant)
          .select_related("shipment", "carrier__party", "license", "consignee_party", "currency"))

    return crud_list(
        request, qs, "scm/compliance/tradedocument/list.html",
        search_fields=["number", "document_number", "consignee_party__name"],
        filters=[("status", "status", False), ("doc_type", "doc_type", False),
                 ("direction", "direction", False), ("shipment", "shipment_id", True),
                 ("license", "license_id", True)],
        extra_context={
            # Every dropdown the filter bar renders gets its choices/queryset here. A filter with no
            # context to render from is the single most common defect in this codebase.
            "status_choices": TradeDocument.STATUS_CHOICES,
            "doctype_choices": TradeDocument.DOC_TYPE_CHOICES,
            "direction_choices": TradeDocument.DIRECTION_CHOICES,
            "shipments": (Shipment.objects.filter(tenant=request.tenant,
                                                  trade_documents__isnull=False)
                          .distinct().order_by("-id")),
            "licenses": (TradeLicense.objects.filter(tenant=request.tenant)
                         .order_by("number")),
        },
    )


@login_required
def tradedocument_create(request):
    return _tradedocument_form(request, instance=None)


@login_required
def tradedocument_edit(request, pk):
    """Editable while draft or amended only — a filed instrument is not corrected in place.

    Once issued, the document is the record of a declaration that was actually made. Changing it
    would rewrite what an authority was told; the route back is to void it and raise the amendment.
    """
    obj = get_object_or_404(TradeDocument, pk=pk, tenant=request.tenant)
    if not obj.is_editable:
        messages.error(request, f"{obj.number} is {obj.get_status_display().lower()} — a filed "
                                "document is amended or voided, not edited.")
        return redirect("scm:tradedocument_detail", pk=pk)
    return _tradedocument_form(request, instance=obj)


def _tradedocument_form(request, instance):
    """Header + line formset committed in ONE ``transaction.atomic()``.

    ``formset.instance = form.instance`` goes after ``form.is_valid()`` and BEFORE
    ``formset.is_valid()``: on create the formset's own instance is an empty ``TradeDocument()``
    with ``tenant_id`` None, and ``TradeDocumentLine.clean()``'s cross-tenant guard on ``item`` /
    ``uom`` asks its parent for the tenant. Without that line the guard finds no tenant to compare
    against and passes everything — silently, on exactly the path a crafted POST exercises.

    This path bypasses ``crud_edit`` (so parent and lines commit together), which means the audit
    row it would have written has to be written by hand — with ``_changed(form)``, not a second copy
    of the redaction list.
    """
    if instance is None and _need_tenant(request):
        return redirect("scm:tradedocument_list")
    is_edit = instance is not None
    if request.method == "POST":
        form = TradeDocumentForm(request.POST, request.FILES, instance=instance,
                                 tenant=request.tenant)
        formset = TradeDocumentLineFormSet(request.POST, instance=instance,
                                           form_kwargs={"tenant": request.tenant})
        form_ok = form.is_valid()
        if form_ok:
            formset.instance = form.instance   # <- load-bearing; see the docstring
        if form_ok and formset.is_valid():
            with transaction.atomic():
                doc = form.save(commit=False)
                doc.tenant = request.tenant
                doc.save()
                formset.instance = doc
                formset.save()
            write_audit_log(request.user, doc, "update" if is_edit else "create", _changed(form))
            messages.success(request, f"{doc.number} saved.")
            return redirect("scm:tradedocument_detail", pk=doc.pk)
    else:
        form = TradeDocumentForm(instance=instance, tenant=request.tenant)
        formset = TradeDocumentLineFormSet(instance=instance,
                                           form_kwargs={"tenant": request.tenant})
    return render(request, "scm/compliance/tradedocument/form.html", {
        "form": form, "formset": formset, "is_edit": is_edit, "obj": instance})


@login_required
def tradedocument_detail(request, pk):
    """The document, its declared lines, and the licence it is drawing on.

    ``lines_total`` costs one aggregate and ``declared_value_matches`` re-reads it — the model
    memoises it per instance, so the two together are one query, not two.

    ``license_warning`` previews the refusal ``tradedocument_issue`` would give, computed from the
    same ``_charge_figures`` + ``can_charge`` pair the verb uses. Showing it here means a filer
    learns the licence is exhausted while the document is still editable rather than at the moment
    they press Issue.
    """
    obj = get_object_or_404(_document_queryset(request.tenant), pk=pk)
    lines = list(obj.lines.select_related("item", "uom"))
    charge_value, charge_quantity = _charge_figures(obj)

    can_issue = obj.status in _ISSUE_FROM
    license_warning = ""
    if can_issue and obj.license_id is not None:
        allowed, reason = obj.license.can_charge(charge_value, charge_quantity)
        if not allowed:
            license_warning = reason

    return render(request, "scm/compliance/tradedocument/detail.html", {
        "obj": obj,
        "lines": lines,
        # The divergence badge is gated on the document HAVING lines: a bill of lading or an
        # insurance certificate legitimately carries none, and `declared_value_matches` reads False
        # for any of them with a non-zero declared value. The property states the arithmetic fact;
        # the page decides when the fact is worth showing.
        "has_lines": bool(lines),
        "lines_total": obj.lines_total,
        "value_matches": obj.declared_value_matches,
        "charge_value": charge_value,
        "charge_quantity": charge_quantity,
        "license_warning": license_warning,
        # The action gates, decided here rather than re-derived in template `{% if %}`s, so a button
        # cannot be offered for a transition the view will refuse.
        "can_edit": obj.is_editable,
        "can_issue": can_issue,
        "can_submit": obj.status in _SUBMIT_FROM,
        "can_accept": obj.status in _ACCEPT_FROM,
        "can_void": obj.status != "void",
    })


@tenant_admin_required
@require_POST
def tradedocument_delete(request, pk):
    """Delete the document and re-derive the licence balance it was drawing on.

    Nothing PROTECTs this row — ``TradeDocumentLine.document`` is ``CASCADE`` and no other model
    points here — so there is no ``ProtectedError`` path to guard. The ``PROTECT`` in 4.12 runs the
    other way: ``TradeDocument.license`` is what stops a licence being deleted out from under the
    documents issued against it, and that guard lives in ``tradelicense_delete``.

    Tenant-admin gated because deleting a filed document destroys the evidence of a declaration that
    was actually made, and takes its declared lines with it. Voiding is the reversible route and
    keeps the history — the message says so when the deleted row was charging a licence.
    """
    obj = get_object_or_404(TradeDocument.objects.select_related("license"), pk=pk,
                            tenant=request.tenant)
    license_id, was_charging = obj.license_id, obj.is_charging
    license_number = obj.license.number if license_id else ""

    with transaction.atomic():
        response = crud_delete(request, model=TradeDocument, pk=pk,
                               success_url="scm:tradedocument_list")
        if license_id is not None:
            # Re-read under the lock rather than reusing the instance fetched above: another issue
            # or void may have moved the counters since, and recompute_usage() writes them.
            licence = (TradeLicense.objects.select_for_update()
                       .filter(pk=license_id, tenant=request.tenant).first())
            if licence is not None:
                licence.recompute_usage()
    if was_charging and license_number:
        messages.info(request, f"The balance on {license_number} was re-derived — that document was "
                               "charged against it.")
    return response


# ==================================================================== the lifecycle verbs
@login_required
@require_POST
def tradedocument_issue(request, pk):
    """Issue the document — and charge its licence, or refuse and charge nothing.

    ``@login_required`` rather than tenant-admin: raising and issuing paperwork is the daily work of
    the person shipping the goods, and the licence balance is the control here, not the role. Void
    and delete stay admin-gated because they undo a filed record.

    ``issue_date`` defaults to today when the form left it blank — it is the date printed on the
    form, and this is the moment the form is issued. It is stated in the diff, so the default is
    visible in the audit trail rather than silent.
    """
    with transaction.atomic():
        obj = get_object_or_404(TradeDocument.objects.select_for_update(), pk=pk,
                                tenant=request.tenant)
        if obj.status not in _ISSUE_FROM:
            messages.error(request, f"{obj.number} is {obj.get_status_display().lower()} — only a "
                                    "draft or an amendment can be issued.")
            return redirect("scm:tradedocument_detail", pk=pk)

        licence = _locked_license(obj, request.tenant)
        if obj.license_id is not None and licence is None:
            # Belt to clean()'s braces: a pointer at a licence that is not in this workspace must
            # not quietly issue an UNCHARGED document, which would understate the balance forever.
            messages.error(request, "The licence this document names is not in this workspace — "
                                    "correct it before issuing.")
            return redirect("scm:tradedocument_detail", pk=pk)

        if licence is not None:
            value, quantity = _charge_figures(obj)
            allowed, reason = licence.can_charge(value, quantity)
            if not allowed:
                # REFUSED, never clamped — see the module docstring.
                messages.error(request, reason)
                return redirect("scm:tradedocument_detail", pk=pk)

        changes = _apply(obj, status="issued", issued_at=timezone.now(), issued_by=request.user,
                         issue_date=obj.issue_date or timezone.localdate())
        if not changes:
            messages.info(request, f"{obj.number} is already issued.")
            return redirect("scm:tradedocument_detail", pk=pk)
        obj.save(update_fields=sorted(changes) + ["updated_at"])
        if licence is not None:
            # Re-derived, not incremented — the counters are a cache with a stated invalidation
            # path, and `+=` is how one drifts permanently.
            licence.recompute_usage()

    write_audit_log(request.user, obj, "update", {"action": "issue", **changes})
    if licence is not None:
        messages.success(request, f"{obj.number} issued and charged to {licence.number}.")
    else:
        messages.success(request, f"{obj.number} issued.")
    return redirect("scm:tradedocument_detail", pk=pk)


@login_required
@require_POST
def tradedocument_submit(request, pk):
    """Record that the issued document has been lodged with the authority or the broker.

    4.12 STORES the filing reference; it does not transmit anything. Real AESDirect / broker / EDI
    filing is deferred and named as such, so nothing on this route may imply a submission actually
    left the building — the message says "recorded as submitted" for that reason.

    No ``recompute_usage()``: ``issued`` and ``submitted`` are both in ``CHARGING_STATUSES``, so the
    balance is unchanged and re-writing the counters would be an UPDATE with nothing to say.
    """
    reference = (request.POST.get("filing_reference") or "").strip()[:64]
    with transaction.atomic():
        obj = get_object_or_404(TradeDocument.objects.select_for_update(), pk=pk,
                                tenant=request.tenant)
        if obj.status not in _SUBMIT_FROM:
            messages.error(request, f"{obj.number} is {obj.get_status_display().lower()} — only an "
                                    "issued document can be submitted.")
            return redirect("scm:tradedocument_detail", pk=pk)
        # A blank input leaves whatever reference is already on the row: this field is also on the
        # edit form, and an empty box must not erase what was captured there.
        payload = {"status": "submitted"}
        if reference:
            payload["filing_reference"] = reference
        changes = _apply(obj, **payload)
        if not changes:
            messages.info(request, f"{obj.number} is already submitted.")
            return redirect("scm:tradedocument_detail", pk=pk)
        obj.save(update_fields=sorted(changes) + ["updated_at"])

    write_audit_log(request.user, obj, "update", {"action": "submit", **changes})
    messages.success(request, f"{obj.number} recorded as submitted"
                              + (f" under {reference}." if reference else "."))
    return redirect("scm:tradedocument_detail", pk=pk)


@login_required
@require_POST
def tradedocument_accept(request, pk):
    """Record the authority's acceptance of a submitted document.

    Terminal for the happy path: an accepted document keeps charging its licence (``accepted`` is in
    ``CHARGING_STATUSES``) and the only move left is void.
    """
    with transaction.atomic():
        obj = get_object_or_404(TradeDocument.objects.select_for_update(), pk=pk,
                                tenant=request.tenant)
        if obj.status not in _ACCEPT_FROM:
            messages.error(request, f"{obj.number} is {obj.get_status_display().lower()} — only a "
                                    "submitted document can be accepted.")
            return redirect("scm:tradedocument_detail", pk=pk)
        changes = _apply(obj, status="accepted")
        if not changes:
            messages.info(request, f"{obj.number} is already accepted.")
            return redirect("scm:tradedocument_detail", pk=pk)
        obj.save(update_fields=sorted(changes) + ["updated_at"])

    write_audit_log(request.user, obj, "update", {"action": "accept", **changes})
    messages.success(request, f"{obj.number} accepted.")
    return redirect("scm:tradedocument_detail", pk=pk)


@tenant_admin_required
@require_POST
def tradedocument_void(request, pk):
    """Void the document and give its licence balance back.

    Admin-gated and reason-required: voiding is what releases a consumed authorisation, and a
    released balance with no recorded reason is a hole in exactly the audit trail this register
    exists to keep. The row itself SURVIVES — voiding is how a filed document's history is kept
    while its effect is undone, which is why it is the recommended alternative to deleting one.
    """
    reason = (request.POST.get("reason") or request.POST.get("void_reason") or "").strip()

    with transaction.atomic():
        # Resolve BEFORE the reason guard — see tradelicense_revoke for why: an early return on a
        # missing reason answered 302 for a cross-tenant or nonexistent pk instead of 404.
        obj = get_object_or_404(TradeDocument.objects.select_for_update(), pk=pk,
                                tenant=request.tenant)
        if not reason:
            messages.error(request, "Give a reason for voiding — it is recorded against the "
                                    "document and it is what explains the released licence balance.")
            return redirect("scm:tradedocument_detail", pk=pk)
        if obj.status == "void":
            messages.info(request, f"{obj.number} is already void.")
            return redirect("scm:tradedocument_detail", pk=pk)
        licence = _locked_license(obj, request.tenant)
        was_charging = obj.is_charging

        changes = _apply(obj, status="void", void_reason=reason)
        if not changes:
            messages.info(request, f"{obj.number} is already void.")
            return redirect("scm:tradedocument_detail", pk=pk)
        obj.save(update_fields=sorted(changes) + ["updated_at"])
        if licence is not None:
            licence.recompute_usage()

    write_audit_log(request.user, obj, "update", {"action": "void", **changes})
    if licence is not None and was_charging:
        messages.success(request, f"{obj.number} voided — {licence.number} now shows "
                                  f"{licence.used_value} used.")
    else:
        messages.success(request, f"{obj.number} voided.")
    return redirect("scm:tradedocument_detail", pk=pk)


@login_required
def tradedocument_print(request, pk):
    """The printable form — ONE generic layout for all thirteen document types.

    Per-type official layouts (the real commercial-invoice and BoL forms) are deferred and named as
    deferred: printing an approximation of a statutory form on the authority's own headings would be
    worse than printing an honest internal one.
    """
    obj = get_object_or_404(_document_queryset(request.tenant), pk=pk)
    return render(request, "scm/compliance/tradedocument/print.html", {
        "obj": obj,
        "lines": list(obj.lines.select_related("item", "uom")),
        "lines_total": obj.lines_total,
        "printed_at": timezone.now(),
    })
