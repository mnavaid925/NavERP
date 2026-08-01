"""SCM 4.12 Contract & Compliance — ``TradeLicense`` views: the licence register and its balance.

**The balance is what makes these views different from ordinary CRUD.** A licence is not paperwork,
it is a quantity — authorised for so much value or so many units, drawn down by every document
issued under it. ``used_value`` / ``used_quantity`` are a CACHE with a stated invalidation path:
every writer of a charging document calls ``recompute_usage()``, and :func:`tradelicense_recompute`
is the manual re-derivation that means drift can never become permanent. Nothing in this module
computes a balance by hand — the arithmetic lives on the model, once, so the tile, the detail card
and the issue-time refusal cannot disagree about how much authority is left.

**Nothing here posts a StockMove and nothing here drafts an accounting document** (L29). A licence
authorises movement; the movement itself is 4.6's, and the money is Module 2's.

**Why the list page WRITES on a GET.** ``refresh_status()`` moves a licence between
``active``/``expiring``/``expired`` from its dates, and a date-derived status has to catch up
somewhere. The roll is bounded to the rows that actually crossed a boundary and lands in ONE
``bulk_update`` — never a ``save()`` per row over an unpaginated scan (the
``_roll_contract_statuses`` precedent, ``SupplierContracts.py:8``). It can only move within
``AUTO_STATUSES``: a ``draft`` / ``applied`` / ``approved`` / ``suspended`` / ``revoked`` licence is
a human decision and a date roll never walks one back.

**The verbs are lock-apply-audit.** Each takes the row ``FOR UPDATE`` inside ``transaction.atomic()``
and re-reads its status *inside the lock*, so a double POST cannot re-stamp an approval date or
revoke twice. Each then builds a ``{field: [before, after]}`` diff and writes ONE audit row; an
EMPTY diff means nothing moved, which is a ``messages.info`` and **no audit row** — an audit trail
whose entries include "changed nothing" is one nobody reads.

Context-var contract (pinned, L7 — the templates are written by a separate agent, so every key each
page consumes is listed here, not just the list var):

* ``scm/compliance/tradelicense/list.html`` — ``object_list`` + ``page_obj`` + ``q`` (from
  ``crud_list``) plus ``status_choices`` (pairs), ``type_choices`` (pairs), ``countries`` (a flat
  list of this tenant's distinct non-blank ``issuing_country`` strings — the third filter dropdown
  has no ``choices`` constant to render from, so it renders from the data), ``expiring_count`` and
  ``expired_count`` (header chips, counted over the WHOLE workspace and not the filtered page, like
  every other ``stats`` header in this app). Filter params are ``q`` / ``status`` /
  ``license_type`` / ``issuing_country``; compare a select's option with ``request.GET.<param>``
  directly — all three are strings, so no ``stringformat`` is needed on this page.
* ``scm/compliance/tradelicense/detail.html`` — ``obj``, ``days_to_expiry`` (``None`` when no expiry
  is recorded), ``expiring_soon``, the balance card's ``remaining_value`` / ``remaining_quantity`` /
  ``utilization_pct`` (each ``None`` when that dimension is UNLIMITED — print an em dash or
  "Unlimited", never a 0 that reads as exhausted) and ``utilization_bar_pct`` (the same figure
  clamped to 0-100 for a progress bar, ``None`` when there is nothing to show — the number itself is
  deliberately NOT clamped, because an over-drawn licence has to read as over-drawn),
  ``is_chargeable`` + ``charge_block_reason`` (whether this licence may authorise new movement right
  now, and the sentence saying why not), ``documents`` + ``documents_truncated`` + ``document_count``
  + ``charging_count``, ``requirements`` + ``requirements_truncated``, and the three action gates
  ``can_submit`` / ``can_approve`` / ``can_revoke``. **Gate the Delete button on
  ``document_count == 0``** — that is exactly the condition :func:`tradelicense_delete` enforces,
  and offering a one-click failure is worse than not offering it. Approve / Revoke / Recompute /
  Delete are tenant-admin only, so wrap those four in
  ``{% if request.user.is_superuser or request.user.is_tenant_admin %}`` (the house idiom; a member
  who is shown a button they will 403 on is the 4.11 finding).
* ``scm/compliance/tradelicense/form.html`` — ``form`` + ``is_edit`` (+ ``obj`` on the edit path).

Badge colours come from ``TradeLicense.STATUS_CSS`` via ``obj.status_css`` — the one place a status
becomes a class. ``badge-success`` / ``badge-warning`` / ``badge-danger`` DO NOT EXIST in theme.css
(L33).
"""
from django.db.models import ProtectedError

from apps.scm.views._common import *  # noqa: F401,F403
from apps.scm.views._helpers import _need_tenant
from apps.scm.forms import TradeLicenseForm
from apps.scm.models import TradeDocument, TradeLicense

#: How many rows each child panel on the detail page shows. The cap is a queryset SLICE, so the
#: DATABASE applies it — it bounds what is fetched, not what is rendered (L40 §1: a guard that first
#: builds the whole thing is the payload, not a guard). One more than the cap is fetched so the page
#: can say it is showing a window without a second COUNT for the panel.
MAX_PANEL_ROWS = 25

#: The status sets each verb accepts, declared ONCE and read by both the guard inside the view and
#: the ``can_*`` flag handed to the template. A button and the route behind it cannot then disagree
#: about whether an action is available (the 4.10 "two of three shapes" finding).
SUBMITTABLE_STATUSES = ("draft",)
#: ``approved`` is included so a licence sitting at "granted but not in force" — imported, seeded, or
#: left there by an earlier press — can be put in force by the same button rather than being stuck.
#: :func:`tradelicense_approve` always lands on ``active`` and then lets ``refresh_status()`` correct
#: it from the dates, because ``approved`` is NOT in ``CHARGEABLE_STATUSES``: a licence parked there
#: can authorise nothing, so leaving one there would be a register with a live authority nobody can
#: use.
APPROVABLE_STATUSES = ("draft", "applied", "approved")


def _json_safe(value):
    """One audit-diff value as something ``AuditLog.changes`` (a ``JSONField``) can actually hold.

    Dates, datetimes and ``Decimal``s are not JSON-serializable, and a verb that stamped one would
    raise while writing the audit row — after its own transaction had already committed. Everything
    that is not a JSON scalar goes in as ``str()``.
    """
    if value is None or isinstance(value, (bool, int, str)):
        return value
    return str(value)


def _changes(obj, before):
    """``{field: [before, after]}`` for every field in ``before`` whose value actually MOVED.

    Returning the pair rather than just the new value is what makes a licence's audit trail readable
    on its own: "status: draft -> applied" answers the question a reader has, where "status:
    applied" makes them go and find the previous row. An empty dict is the caller's signal that the
    POST changed nothing — see the module docstring for why that must not write an audit row.
    """
    out = {}
    for name, old in before.items():
        new = getattr(obj, name)
        if old != new:
            out[name] = [_json_safe(old), _json_safe(new)]
    return out


def _roll_license_statuses(tenant):
    """Move active <-> expiring <-> expired for whichever licences crossed a date boundary.

    ONE ``bulk_update`` over the rows that actually changed — not a ``save()`` per row on an
    unpaginated scan of every licence in the workspace (the ``_roll_contract_statuses`` precedent).
    ``refresh_status(save=False)`` leaves the new value on the instance for exactly this.

    A tenant-less caller (the superuser, ``tenant=None``) filters on a non-nullable FK and matches
    nothing, so this is a single cheap SELECT and no writes.
    """
    changed = []
    # bulk_update never calls pre_save, so auto_now does NOT fire: updated_at has to be stamped by
    # hand or the column is written back with its stale in-memory value, silently backdating a row
    # that just changed. Same fix ComplianceRequirements._roll_requirement_statuses carries.
    stamp = timezone.now()
    for lic in TradeLicense.objects.filter(tenant=tenant, status__in=TradeLicense.AUTO_STATUSES):
        old = lic.status
        lic.refresh_status(save=False)
        if lic.status != old:
            lic.updated_at = stamp
            changed.append(lic)
    if changed:
        with transaction.atomic():
            TradeLicense.objects.bulk_update(changed, ["status", "updated_at"])
    return len(changed)


def _stamp_within_ladder(candidate, *, not_before=None, not_after=None):
    """``candidate`` when it fits the model's application -> issue -> expiry ladder, else ``None``.

    The verbs fill in a missing ``application_date`` / ``issue_date`` with today, which is right on
    every ordinary licence and WRONG on one whose other dates are already in the past: ``save()``
    does not run ``clean()``, so a helpful default would quietly write a row the form would refuse
    (expires before it was applied for). Where today does not fit, the date is left empty for a
    human to type — a blank is honest, an inverted ladder is not.
    """
    if not_before is not None and candidate < not_before:
        return None
    if not_after is not None and candidate > not_after:
        return None
    return candidate


# ============================================================================ the register (CRUD)
@login_required
def tradelicense_list(request):
    """Search + three filters over the workspace's licences, with the expiry roll applied first.

    ``select_related`` covers the three FKs a row renders (``holder_party``, ``end_user_party``,
    ``currency``); without it a page of 15 licences is up to 45 extra queries for three columns.

    Every filter is applied by ``crud_list``, which paginates — a filter applied afterwards would
    page over the unfiltered set and quietly show the wrong rows on page 2. All three are string
    columns, so none of them needs L11's int-FK guard (there is no ``is_int=True`` filter on this
    page); a junk value simply matches nothing rather than raising.
    """
    # First, so the badges, the chips and the filtered set all read the same post-roll statuses.
    _roll_license_statuses(request.tenant)

    qs = (TradeLicense.objects.filter(tenant=request.tenant)
          .select_related("holder_party", "end_user_party", "currency"))

    # ONE aggregate for both header chips, over the WHOLE workspace rather than the filtered page:
    # "3 expiring" is a workspace fact somebody has to act on, and recomputing it per filter would
    # make the number change as you browse.
    chips = TradeLicense.objects.filter(tenant=request.tenant).aggregate(
        expiring=Count("id", filter=Q(status="expiring")),
        expired=Count("id", filter=Q(status="expired")),
    )

    # `issuing_country` is free text (no CHOICES to render from), so the dropdown is built from the
    # values this workspace actually holds. `order_by` is stated explicitly and is load-bearing:
    # Meta.ordering is ["expiry_date", "-id"], and DISTINCT over a values_list carrying an unrelated
    # ORDER BY column returns duplicates.
    countries = (TradeLicense.objects.filter(tenant=request.tenant)
                 .exclude(issuing_country="")
                 .order_by("issuing_country")
                 .values_list("issuing_country", flat=True)
                 .distinct())

    return crud_list(
        request, qs, "scm/compliance/tradelicense/list.html",
        search_fields=["number", "license_number", "title", "issuing_authority"],
        filters=[("status", "status", False), ("license_type", "license_type", False),
                 ("issuing_country", "issuing_country", False)],
        extra_context={
            "status_choices": TradeLicense.STATUS_CHOICES,
            "type_choices": TradeLicense.LICENSE_TYPE_CHOICES,
            "countries": countries,
            "expiring_count": chips["expiring"],
            "expired_count": chips["expired"],
        },
    )


@login_required
def tradelicense_create(request):
    """Register a licence. ``crud_create`` stamps the tenant, audits, and refuses a tenant-less user."""
    if _need_tenant(request):
        return redirect("scm:tradelicense_list")
    return crud_create(request, form_class=TradeLicenseForm,
                       template="scm/compliance/tradelicense/form.html",
                       success_url="scm:tradelicense_list")


@login_required
def tradelicense_edit(request, pk):
    """Editable at any status — deliberately, and narrowly.

    A licence record tracks an EXTERNAL authority's grant, and authorities amend, extend and
    re-scope what they granted; a register that froze the row the moment it went live would push
    those corrections into the notes field. What an edit cannot do is move the licence: ``status``,
    the four decision stamps and both usage counters are all off the form, so this screen can only
    correct what the licence SAYS, never what it has authorised or how much of it is left.
    """
    return crud_edit(request, model=TradeLicense, pk=pk, form_class=TradeLicenseForm,
                     template="scm/compliance/tradelicense/form.html",
                     success_url="scm:tradelicense_list")


@login_required
def tradelicense_detail(request, pk):
    """The licence, its balance card, what has been charged to it and what it obliges us to prove."""
    obj = get_object_or_404(
        TradeLicense.objects.select_related("holder_party", "end_user_party", "currency",
                                            "document", "approved_by"),
        pk=pk, tenant=request.tenant)
    # This one row's date-driven status, caught up on the way in — the `contract_detail` precedent.
    # A no-op unless it actually crossed a boundary, and it can only move within AUTO_STATUSES.
    obj.refresh_status()

    # One more than the cap is fetched so the page can say it is showing a window. The explicit
    # `tenant=` is redundant (the related manager already constrains by licence, which implies the
    # tenant) and is stated anyway so this page holds to the module-wide rule mechanically.
    documents = list(obj.trade_documents.filter(tenant=request.tenant)
                     .select_related("consignee_party", "currency", "shipment")[:MAX_PANEL_ROWS + 1])
    documents_truncated = len(documents) > MAX_PANEL_ROWS
    del documents[MAX_PANEL_ROWS:]

    # ONE aggregate for both figures. `charging_count` is the evidence behind the balance card:
    # `used_value` counts CHARGING_STATUSES documents only, so a page showing a total that included
    # drafts and voids would make the number look wrong when it is right.
    doc_counts = obj.trade_documents.filter(tenant=request.tenant).aggregate(
        total=Count("id"),
        charging=Count("id", filter=Q(status__in=TradeDocument.CHARGING_STATUSES)),
    )

    requirements = list(obj.compliance_requirements.filter(tenant=request.tenant)
                        .select_related("owner")[:MAX_PANEL_ROWS + 1])
    requirements_truncated = len(requirements) > MAX_PANEL_ROWS
    del requirements[MAX_PANEL_ROWS:]

    # The same question the issue route asks before it charges anything, asked with no charge: is
    # this licence usable at all right now? Called with no arguments it tests the status, the real
    # expiry date (not the cached word) and whether the licence is already over-drawn.
    is_chargeable, charge_block_reason = obj.can_charge()

    utilization_pct = obj.utilization_pct
    return render(request, "scm/compliance/tradelicense/detail.html", {
        "obj": obj,
        "days_to_expiry": obj.days_to_expiry(),
        "expiring_soon": obj.is_expiring_soon(),
        # None where the licence is UNLIMITED in that dimension — the template prints an em dash.
        # A confident 0 in a balance card is worse than an honest blank (the 4.11 lesson).
        "remaining_value": obj.remaining_value,
        "remaining_quantity": obj.remaining_quantity,
        "utilization_pct": utilization_pct,
        # Clamped ONLY for the bar's width. `utilization_pct` itself is passed unclamped above,
        # because an over-drawn licence must read as over-drawn rather than as a tidy full bar.
        "utilization_bar_pct": (None if utilization_pct is None
                                else int(min(utilization_pct, Decimal("100")))),
        "is_chargeable": is_chargeable,
        "charge_block_reason": charge_block_reason,
        "documents": documents,
        "documents_truncated": documents_truncated,
        "document_count": doc_counts["total"],
        "charging_count": doc_counts["charging"],
        "requirements": requirements,
        "requirements_truncated": requirements_truncated,
        # Read from the module constants the verbs themselves guard on — see their comment.
        "can_submit": obj.status in SUBMITTABLE_STATUSES,
        "can_approve": obj.status in APPROVABLE_STATUSES,
        "can_revoke": obj.status != "revoked",
    })


@tenant_admin_required
@require_POST
def tradelicense_delete(request, pk):
    """Delete a licence — refused while anything was ever papered under it.

    ``TradeDocument.license`` is ``PROTECT`` deliberately: the record of what moved under a licence
    is the evidence the whole category exists to keep, and losing it must not be one click away. So
    this pre-checks and refuses with a sentence naming the blocker, and ALSO catches
    ``ProtectedError`` — the pre-check is the good message, the catch is what stops a document
    issued between the check and the delete from becoming an uncaught 500 (the 4.10
    ``currency_delete`` finding, priced in advance).

    ``ComplianceRequirement.license`` is ``SET_NULL`` by contrast, so obligations SURVIVE with their
    proof history and merely lose the link. That is a real consequence of pressing Delete, so it is
    said out loud — and only after the delete actually succeeded.
    """
    obj = get_object_or_404(TradeLicense, pk=pk, tenant=request.tenant)

    charged = obj.trade_documents.count()
    if charged:
        messages.error(
            request,
            f"{obj.number} still authorises {charged} trade document(s) and cannot be deleted — "
            "what moved under a licence is the record this register exists to keep. Revoke the "
            "licence instead; a revoked licence stops authorising new movement and keeps its "
            "history.")
        return redirect("scm:tradelicense_detail", pk=pk)

    unlinked = obj.compliance_requirements.count()
    try:
        with transaction.atomic():
            response = crud_delete(request, model=TradeLicense, pk=pk,
                                   success_url="scm:tradelicense_list")
    except ProtectedError as exc:
        blockers = sorted({protected._meta.verbose_name for protected in exc.protected_objects})
        messages.error(request, f"{obj.number} is still referenced by {', '.join(blockers)} and "
                                "cannot be deleted — revoke it instead.")
        return redirect("scm:tradelicense_detail", pk=pk)
    if unlinked:
        messages.info(request, f"{unlinked} compliance requirement(s) lost their link to "
                               f"{obj.number}. The obligations and their check history survive — "
                               "re-point them at the replacement licence.")
    return response


# ================================================================================== the lifecycle
@login_required
@require_POST
def tradelicense_submit(request, pk):
    """Record that the application went to the authority: draft -> applied.

    Ordinary work, so ``@login_required`` rather than the admin gate the decision verbs carry —
    lodging an application commits nothing and authorises nothing. The transport is DEFERRED and
    deliberately so (the ``warrantyclaim_submit`` posture): 4.12 records the fact, it does not file.
    """
    with transaction.atomic():
        obj = get_object_or_404(TradeLicense.objects.select_for_update(),
                                pk=pk, tenant=request.tenant)
        # Re-read inside the lock: a double POST must not re-stamp the application date, which is
        # the date the whole application ladder is measured from.
        if obj.status not in SUBMITTABLE_STATUSES:
            messages.info(request, f"{obj.number} has already been submitted — it is "
                                   f"{obj.get_status_display().lower()}.")
            return redirect("scm:tradelicense_detail", pk=pk)

        before = {"status": obj.status, "application_date": obj.application_date}
        obj.status = "applied"
        fields = ["status", "updated_at"]
        if obj.application_date is None:
            # Only when today does not invert the ladder — see _stamp_within_ladder.
            stamped = _stamp_within_ladder(
                timezone.localdate(),
                not_after=min([d for d in (obj.issue_date, obj.expiry_date) if d], default=None))
            if stamped is not None:
                obj.application_date = stamped
                fields.append("application_date")
        obj.save(update_fields=fields)
        changes = _changes(obj, before)

    write_audit_log(request.user, obj, "update", {"action": "submit", **changes})
    messages.success(request, f"{obj.number} marked as applied for with "
                              f"{obj.issuing_authority or 'the issuing authority'}. Nothing was "
                              "transmitted — this records the application, it does not file it.")
    return redirect("scm:tradelicense_detail", pk=pk)


@tenant_admin_required
@require_POST
def tradelicense_approve(request, pk):
    """Record the authority's grant and put the licence IN FORCE.

    Admin-gated because this is the moment a licence starts authorising movement: from here
    ``can_charge()`` says yes and documents may be issued against the balance.

    It lands on ``active`` and then immediately calls ``refresh_status()``, which may correct it to
    ``expiring`` or ``expired`` from the dates — the ``contract_activate`` precedent. It does NOT
    park the licence at ``approved``: that status is not in ``CHARGEABLE_STATUSES`` and no date roll
    ever leaves it (``AUTO_STATUSES`` is the active/expiring/expired trio), so a licence left there
    would be a granted authority nobody could use and nothing could revive.
    """
    with transaction.atomic():
        obj = get_object_or_404(TradeLicense.objects.select_for_update(),
                                pk=pk, tenant=request.tenant)
        if obj.status in ("revoked", "suspended"):
            messages.error(request, f"{obj.number} is {obj.get_status_display().lower()} — a "
                                    "withdrawn authority is re-registered, not re-approved.")
            return redirect("scm:tradelicense_detail", pk=pk)
        # Re-read inside the lock: a double POST must not re-stamp who approved it and when.
        if obj.status not in APPROVABLE_STATUSES:
            messages.info(request, f"{obj.number} is already in force "
                                   f"({obj.get_status_display().lower()}).")
            return redirect("scm:tradelicense_detail", pk=pk)

        before = {"status": obj.status, "issue_date": obj.issue_date,
                  "approved_at": obj.approved_at, "approved_by": obj.approved_by}
        obj.status = "active"
        obj.approved_at = timezone.now()
        obj.approved_by = request.user
        fields = ["status", "approved_at", "approved_by", "updated_at"]
        if obj.issue_date is None:
            stamped = _stamp_within_ladder(timezone.localdate(),
                                           not_before=obj.application_date,
                                           not_after=obj.expiry_date)
            if stamped is not None:
                obj.issue_date = stamped
                fields.append("issue_date")
        obj.save(update_fields=fields)
        # The dates get the last word: a licence approved after it lapsed is expired, not active.
        obj.refresh_status()
        changes = _changes(obj, before)

    write_audit_log(request.user, obj, "update", {"action": "approve", **changes})
    messages.success(request, f"{obj.number} approved and in force — "
                              f"{obj.get_status_display().lower()}.")
    if obj.status == "expired":
        messages.warning(request, f"Its expiry date ({obj.expiry_date}) has already passed, so it "
                                  "cannot authorise new movement. Correct the dates or register the "
                                  "replacement licence.")
    elif obj.status == "expiring":
        messages.warning(request, f"It lapses in {obj.days_to_expiry()} day(s) — start the renewal "
                                  "now if movement is still expected under it.")
    return redirect("scm:tradelicense_detail", pk=pk)


@tenant_admin_required
@require_POST
def tradelicense_revoke(request, pk):
    """Withdraw a licence. Admin-gated, reason-required, and it does NOT unwind the balance.

    Everything already issued under the licence stays charged to it, deliberately: the balance is
    the record of what was authorised at the time, and re-deriving it downward on revocation would
    erase the evidence that the movement happened. What revocation stops is NEW movement —
    ``revoked`` is not in ``CHARGEABLE_STATUSES``, so ``can_charge()`` refuses from here on.
    """
    # `reason` OR `revocation_reason`: the sibling void action accepts both spellings, and a caller
    # that guesses the short one here would otherwise get a silent no-op redirect.
    reason = (request.POST.get("reason")
              or request.POST.get("revocation_reason") or "").strip()

    with transaction.atomic():
        # Resolve BEFORE the reason guard. Returning early on a missing reason meant a reasonless
        # POST to any pk — another tenant's, or one that does not exist — answered 302 instead of
        # 404, so the "cross-tenant is always a 404" invariant held only when a reason was supplied.
        obj = get_object_or_404(TradeLicense.objects.select_for_update(),
                                pk=pk, tenant=request.tenant)
        if not reason:
            messages.error(request, "Give a reason when revoking a licence — it is the record of "
                                    "why the authority was withdrawn.")
            return redirect("scm:tradelicense_detail", pk=pk)
        # Re-read inside the lock: a second revocation would overwrite the first reason and date
        # without trace, and those are what an auditor reads.
        if obj.status == "revoked":
            messages.info(request, f"{obj.number} was already revoked on "
                                   f"{obj.revoked_at:%Y-%m-%d}." if obj.revoked_at
                                   else f"{obj.number} is already revoked.")
            return redirect("scm:tradelicense_detail", pk=pk)

        before = {"status": obj.status, "revoked_at": obj.revoked_at}
        obj.status = "revoked"
        obj.revoked_at = timezone.now()
        obj.revocation_reason = reason[:2000]
        obj.save(update_fields=["status", "revoked_at", "revocation_reason", "updated_at"])
        # Counted inside the lock so the warning below describes the state that was just frozen.
        live = obj.trade_documents.filter(status__in=TradeDocument.CHARGING_STATUSES).count()
        changes = _changes(obj, before)

    write_audit_log(request.user, obj, "update",
                    {"action": "revoke", "reason": reason[:200], **changes})
    messages.success(request, f"{obj.number} revoked — it can no longer authorise new movement.")
    if live:
        messages.warning(request, f"{live} document(s) remain charged against it. Its balance still "
                                  "shows what was authorised before the revocation, which is the "
                                  "record — it is not re-derived downward.")
    return redirect("scm:tradelicense_detail", pk=pk)


@tenant_admin_required
@require_POST
def tradelicense_recompute(request, pk):
    """Re-derive ``used_value`` / ``used_quantity`` from the documents charged to this licence.

    This is the stated invalidation path that lets the two counters be columns at all. Every writer
    of a charging document already calls ``recompute_usage()``; this is the button that fixes drift
    from a direct DB edit, a data import or a bug that has since been fixed — so a wrong balance can
    never become permanent.

    Admin-gated because the balance is what the issue-time refusal is computed from: moving it moves
    what the workspace is allowed to ship. When the re-derivation finds NOTHING to change — the
    normal, healthy case — that is a ``messages.info`` and no audit row, because "recomputed,
    identical" is noise in a trail somebody has to read.
    """
    with transaction.atomic():
        obj = get_object_or_404(TradeLicense.objects.select_for_update(),
                                pk=pk, tenant=request.tenant)
        before = {"used_value": obj.used_value, "used_quantity": obj.used_quantity}
        # Two single-grain aggregates on the model, never a per-document loop — and never one
        # aggregate over both, which would join the lines in and multiply every declared value by
        # its line count. See TradeLicense.recompute_usage.
        obj.recompute_usage(save=True)
        changes = _changes(obj, before)

    if not changes:
        # Count only the documents that actually CHARGE the licence — used_value sums exactly those.
        # A plain .count() here would report a licence with two drafts and one issued document as
        # "3 charged", i.e. a number the balance beside it cannot be reconciled with.
        charging = obj.trade_documents.filter(status__in=TradeDocument.CHARGING_STATUSES).count()
        messages.info(request, f"{obj.number} was already in step with its documents — "
                               f"{obj.used_value} used across {charging} "
                               "charged document(s). Nothing changed.")
        return redirect("scm:tradelicense_detail", pk=pk)

    write_audit_log(request.user, obj, "update", {"action": "recompute_usage", **changes})
    remaining = obj.remaining_value
    messages.success(request, f"{obj.number} re-derived from its documents: {obj.used_value} used"
                              + (f", {remaining} of {obj.authorized_value} left."
                                 if remaining is not None else " (no value cap on this licence)."))
    return redirect("scm:tradelicense_detail", pk=pk)
