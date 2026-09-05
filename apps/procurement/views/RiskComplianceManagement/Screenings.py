"""Procurement 6.17 Risk & Compliance Management — ComplianceScreening views.

Nine routes: the register, one detail page, capture/amend/delete, the three decision verbs
(clear / escalate / block) and the standalone **re-screening due** board.

Discipline a reviewer will otherwise go looking for:

* **Every queryset is ``filter(tenant=request.tenant)``** — never ``.all()``. This model has its
  own tenant column, so every object is fetched ``get_object_or_404(..., tenant=request.tenant)``.
* **Ordinary CRUD is ``@login_required``; every decision adds ``@tenant_admin_required`` and
  ``@require_POST``** (in that order, L27). Clearing a supplier past a sanctions hit, or recording
  a block, is not something a GET should be able to do.
* **Every verb runs the row under ``select_for_update()`` inside ``transaction.atomic()``**, so
  two officers clicking on the same screening cannot both audit a state change.
* **``allowed_actions`` mirrors the decorators exactly** — a hidden button and a refused POST
  always agree. ``Clear`` is withheld while any hit is open, which is the same guard
  :meth:`ComplianceScreening.clear` re-runs against the database.
* **This module writes NOTHING to the spine and nothing to ``apps.accounting``** (L29): no
  auto-suspension, no invoice block, no PO hold. ``block`` records a decision and may STAMP an
  existing 6.4 ``VendorSuspension``; raising one is the 6.4 register's job and the page links out
  to it.

``screening_batch`` is deliberately not implemented — see the note in
``apps/procurement/urls/RiskComplianceManagement/Screenings.py``.
"""
from datetime import date, timedelta

from django.db import transaction
from django.db.models import Count, Q
from django.urls import reverse

from apps.core.crud import _changed, as_db_int
from apps.core.models import Party
from apps.procurement.forms.RiskComplianceManagement.Screenings import (
    ComplianceScreeningForm, ScreeningHitForm)
# NOT-YET-WIRED entities of this SAME sub-module: import the entity MODULE directly, never
# ``from apps.procurement.models import X`` — the sub-package is not wired until the Integrator
# lands it, and a package-level re-export would be a star-import cycle at URLconf import time.
from apps.procurement.models.RiskComplianceManagement.Screenings import (
    CHECKPOINT_CHOICES, DISPOSITION_CHOICES, LIST_SOURCE_CHOICES, RESULT_CHOICES, STATUS_CHOICES,
    TERMINAL_DISPOSITIONS, ComplianceScreening, ScreeningHit)
from apps.procurement.models.VendorManagement.VendorSuspensions import VendorSuspension
from apps.procurement.views._common import *  # noqa: F401,F403

TEMPLATE_LIST = "procurement/riskcompliance/screening/list.html"
TEMPLATE_DETAIL = "procurement/riskcompliance/screening/detail.html"
TEMPLATE_FORM = "procurement/riskcompliance/screening/form.html"
TEMPLATE_RESCREEN = "procurement/riskcompliance/rescreening_due.html"

#: How far ahead the re-screening board's "due soon" card looks.
RESCREEN_DUE_SOON_DAYS = 30

#: The dispositions a hit may be adjudicated TO — the picker on the detail page never offers
#: ``open``, because un-adjudicating a hit is not something this module does.
_TERMINAL_DISPOSITION_CHOICES = [(value, label) for value, label in DISPOSITION_CHOICES
                                 if value in TERMINAL_DISPOSITIONS]

#: Every hop a register row (or its own ``__str__``) walks.
_ROW_RELATIONS = ("party",)

#: Every hop the detail page walks.
_DETAIL_RELATIONS = _ROW_RELATIONS + (
    "evidence", "suspension", "suspension__supplier", "screened_by", "decided_by")


# -- shared helpers ------------------------------------------------------------------------------

def _is_admin(request):
    """Mirrors ``@tenant_admin_required`` exactly, so a hidden button and a refused POST agree."""
    return bool(request.user.is_superuser or getattr(request.user, "is_tenant_admin", False))


def _need_tenant(request, what):
    """The superuser has no workspace by design; say so instead of rendering an empty page."""
    if request.tenant is None:
        messages.error(request, f"Select a tenant workspace to {what}.")
        return redirect("dashboard:home")
    return None


def _screening_qs(request):
    return (ComplianceScreening.objects.filter(tenant=request.tenant)
            .select_related(*_ROW_RELATIONS))


def _screenable_parties(tenant):
    """The parties that can be screened: this workspace's suppliers and vendors."""
    if tenant is None:
        return Party.objects.none()
    return (Party.objects.filter(tenant=tenant, roles__role__in=("supplier", "vendor"))
            .distinct().order_by("name"))


def _stats(tenant, today):
    """The four register stat cards.

    Counted over the WHOLE workspace, not the filtered page: a stat card answers "how much
    compliance work is outstanding?", which must not change because somebody typed a search.

    ``open_hits`` is a LIVE count over the child table rather than a SUM of the cached
    ``open_hit_count`` columns — the same discipline the disposition guard follows, so the number
    on the card and the number the gate enforces can never disagree.
    """
    stats = ComplianceScreening.objects.filter(tenant=tenant).aggregate(
        pending=Count("id", filter=Q(status="pending_review")),
        blocked=Count("id", filter=Q(status="blocked")),
        rescreen_due=Count("id", filter=Q(status="cleared", next_rescreen_on__lte=today)),
    )
    stats["open_hits"] = ScreeningHit.objects.filter(
        screening__tenant=tenant, disposition="open").count()
    return stats


def _refuse_terminal(obj, verb):
    return (f"{obj.number} is already {obj.get_status_display().lower()} and cannot be {verb}. "
            f"A decided screening is evidence — record a NEW screening instead.")


def _decision(request, pk, action, invoke, success, refuse, resolve_extra=None):
    """One decision verb: lock the row, call it, report and audit.

    ``invoke`` re-checks its own guard on the model and returns a bool — the row lock is what
    makes that guard meaningful against two concurrent clicks, and the model method is what makes
    a direct POST as safe as a click. ``resolve_extra`` runs INSIDE the lock and may return an
    error string to abort (that is how ``block`` validates the suspension it was handed).
    """
    guard = _need_tenant(request, "decide compliance screenings")
    if guard is not None:
        return guard

    changes = {"action": action}
    with transaction.atomic():
        obj = get_object_or_404(ComplianceScreening.objects.select_for_update(),
                                pk=pk, tenant=request.tenant)
        extra = {}
        if resolve_extra is not None:
            error, extra = resolve_extra(obj)
            if error:
                messages.error(request, error)
                return redirect("procurement:screening_detail", pk=pk)
        if not invoke(obj, extra):
            messages.error(request, refuse(obj))
            return redirect("procurement:screening_detail", pk=pk)
        changes.update({key: str(value) for key, value in extra.items() if value is not None})

    write_audit_log(request.user, obj, "update", changes)
    messages.success(request, success(obj))
    return redirect("procurement:screening_detail", pk=pk)


# -- the register --------------------------------------------------------------------------------

@login_required
def screening_list(request):
    """The screening register — every sanctions lookup in the workspace, newest first."""
    guard = _need_tenant(request, "review compliance screenings")
    if guard is not None:
        return guard
    return crud_list(
        request,
        _screening_qs(request),
        TEMPLATE_LIST,
        search_fields=["number", "party__name", "reference", "notes"],
        # (get_param, orm_lookup, is_int). The int one goes through crud_list's as_db_int guard,
        # so ?party=abc / ?party=999999999999999999999 skip the filter instead of 500ing; the
        # four enum ones are validated against the model's own CHOICES before they narrow, so a
        # stale bookmark cannot silently empty the register (L11).
        filters=[("party", "party_id", True),
                 ("list_source", "list_source", False),
                 ("checkpoint", "checkpoint", False),
                 ("result", "result", False),
                 ("status", "status", False)],
        extra_context={
            "list_source_choices": LIST_SOURCE_CHOICES,
            "checkpoint_choices": CHECKPOINT_CHOICES,
            "result_choices": RESULT_CHOICES,
            "status_choices": STATUS_CHOICES,
            "parties": _screenable_parties(request.tenant),
            "stats": _stats(request.tenant, timezone.localdate()),
            "is_admin": _is_admin(request),
            "retention_note": ComplianceScreening.RETENTION_NOTE,
        },
    )


@login_required
def screening_detail(request, pk):
    """One screening: what was searched, what came back, and what may still be decided."""
    obj = get_object_or_404(ComplianceScreening.objects.select_related(*_DETAIL_RELATIONS),
                            pk=pk, tenant=request.tenant)
    is_admin = _is_admin(request)

    # ONE query for the hits; the open subset is derived in Python from the same list rather than
    # costing a second round trip. This is a DISPLAY value — the gate that actually matters is
    # re-run against the database inside ComplianceScreening.clear().
    hits = list(obj.hits.select_related("disposed_by").all())
    open_hits = [hit for hit in hits if hit.is_open]

    # Each entry mirrors the decorator on the route it points at, so the page never offers a
    # button that would 403 — and Clear is withheld while a hit is unadjudicated, which is the
    # same guard the model re-runs. ``key`` is what lets the template render each verb's OWN
    # fields (clear takes an optional note, escalate and block require one, block also offers the
    # suspension picker) while the VIEW stays the single source of truth for what is allowed.
    allowed_actions = []
    if is_admin and not obj.is_terminal and not open_hits:
        allowed_actions.append({"key": "clear",
                                "url": reverse("procurement:screening_clear", args=[obj.pk]),
                                "label": "Clear", "css": "btn-primary", "icon": "check-circle"})
    if is_admin and obj.status == "pending_review":
        allowed_actions.append({"key": "escalate",
                                "url": reverse("procurement:screening_escalate", args=[obj.pk]),
                                "label": "Escalate", "css": "btn-outline", "icon": "arrow-up"})
    if is_admin and obj.is_open:
        allowed_actions.append({"key": "block",
                                "url": reverse("procurement:screening_block", args=[obj.pk]),
                                "label": "Record block", "css": "btn-danger", "icon": "ban"})

    # The 6.4 register row currently blocking this supplier, if any. Delegated whole to
    # VendorSuspension.blocking_for so this page and the enforcement point can never disagree;
    # rendered as a list because that is what the page shows, and it doubles as the picker the
    # block verb offers (there is nothing else honest to link a block decision to).
    blocking = obj.blocking_suspension()

    return render(request, TEMPLATE_DETAIL, {
        "obj": obj,
        "hits": hits,
        "open_hits": open_hits,
        "allowed_actions": allowed_actions,
        "blocking_suspensions": [blocking] if blocking is not None else [],
        "hit_form": ScreeningHitForm(tenant=request.tenant),
        # Terminal dispositions only — the inline picker never offers "open".
        "disposition_choices": _TERMINAL_DISPOSITION_CHOICES,
        "is_admin": is_admin,
        "retention_note": ComplianceScreening.RETENTION_NOTE,
    })


# -- capture / amend -------------------------------------------------------------------------------

def _screening_form(request, instance=None):
    """Capture or amend one screening.

    Hand-rolled rather than ``crud_create`` / ``crud_edit`` because it stamps ``screened_by`` from
    the session: a form field for "who ran this check" is an attribution anybody could forge, and
    amending a screening must not silently transfer it either.

    The context is exactly the ``crud_*`` contract — ``form`` + ``is_edit``, plus ``obj`` on the
    edit path only — so the one template behaves identically on both routes (L7).
    """
    is_edit = instance is not None

    if request.method == "POST":
        form = ComplianceScreeningForm(request.POST, request.FILES, instance=instance,
                                       tenant=request.tenant)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.tenant = request.tenant
            if not is_edit:
                obj.screened_by = request.user if request.user.is_authenticated else None
            obj.save()
            write_audit_log(request.user, obj, "update" if is_edit else "create", _changed(form))
            messages.success(request, f"Screening {obj.number} saved.")
            return redirect("procurement:screening_detail", pk=obj.pk)
    else:
        form = ComplianceScreeningForm(instance=instance, tenant=request.tenant)

    ctx = {"form": form, "is_edit": is_edit}
    if is_edit:
        ctx["obj"] = instance
    return render(request, TEMPLATE_FORM, ctx)


@login_required
def screening_create(request):
    """Record a sanctions / denied-party lookup that was run against a supplier."""
    guard = _need_tenant(request, "record compliance screenings")
    if guard is not None:
        return guard
    return _screening_form(request)


@login_required
def screening_edit(request, pk):
    """Amend a screening — refused once it has been decided."""
    obj = get_object_or_404(ComplianceScreening, pk=pk, tenant=request.tenant)
    if obj.is_terminal:
        # Amending the lookup behind a recorded decision would rewrite the evidence that decision
        # rests on. Record a new screening instead.
        messages.error(request, _refuse_terminal(obj, "edited"))
        return redirect("procurement:screening_detail", pk=pk)
    return _screening_form(request, instance=obj)


@login_required
@tenant_admin_required
@require_POST
def screening_delete(request, pk):
    """Admin-gated: deleting a screening erases the proof a check was ever performed."""
    obj = get_object_or_404(ComplianceScreening, pk=pk, tenant=request.tenant)
    if obj.is_terminal:
        messages.error(request, _refuse_terminal(obj, "deleted"))
        return redirect("procurement:screening_detail", pk=pk)
    return crud_delete(request, model=ComplianceScreening, pk=pk,
                       success_url="procurement:screening_list")


# -- the three decision verbs -----------------------------------------------------------------------

@login_required
@tenant_admin_required
@require_POST
def screening_clear(request, pk):
    """Clear a supplier. Refused while any hit is still unadjudicated."""
    note = (request.POST.get("note") or "").strip()
    return _decision(
        request, pk, "clear",
        invoke=lambda obj, extra: obj.clear(request.user, note),
        success=lambda obj: (
            f"{obj.number} cleared."
            + (f" Next re-screen due {obj.next_rescreen_on:%b %d, %Y}." if obj.next_rescreen_on
               else "")),
        refuse=lambda obj: (
            _refuse_terminal(obj, "cleared") if obj.is_terminal else
            f"{obj.number} still has {obj.hits.filter(disposition='open').count()} unadjudicated "
            f"hit(s). Every hit must be dispositioned before a supplier can be cleared."),
    )


@login_required
@tenant_admin_required
@require_POST
def screening_escalate(request, pk):
    """Escalate a screening for a compliance decision. The note is required."""
    note = (request.POST.get("note") or "").strip()
    if not note:
        messages.error(request, "Say why this screening is being escalated.")
        return redirect("procurement:screening_detail", pk=pk)
    return _decision(
        request, pk, "escalate",
        invoke=lambda obj, extra: obj.escalate(request.user, note),
        success=lambda obj: f"{obj.number} escalated for compliance review.",
        refuse=lambda obj: (
            _refuse_terminal(obj, "escalated") if obj.is_terminal else
            f"{obj.number} is already escalated."),
    )


@login_required
@tenant_admin_required
@require_POST
def screening_block(request, pk):
    """Record that this supplier was blocked on the strength of this screening.

    Creates NOTHING: the block itself lives in the 6.4 suspension register, and this verb only
    records the decision plus — optionally — a pointer at the suspension already in force. The
    detail page links to ``procurement:vsu_create`` when there is none to point at.
    """
    note = (request.POST.get("note") or "").strip()
    if not note:
        messages.error(request, "Record the case for blocking this supplier.")
        return redirect("procurement:screening_detail", pk=pk)
    suspension_id = as_db_int(request.POST.get("suspension"))

    def resolve_suspension(obj):
        """Resolve the optional suspension INSIDE the lock, scoped to tenant AND to this party.

        A suspension against a different supplier is not evidence for blocking this one, so a
        pk that does not resolve aborts the whole POST rather than being silently dropped — a
        dropped link would leave a block with no stated basis.
        """
        if not suspension_id:
            return None, {}
        suspension = VendorSuspension.objects.filter(
            pk=suspension_id, tenant=request.tenant, supplier_id=obj.party_id).first()
        if suspension is None:
            return ("That suspension is not on file for this supplier in this workspace.", {})
        return None, {"suspension": suspension}

    return _decision(
        request, pk, "block",
        invoke=lambda obj, extra: obj.block(request.user, note, extra.get("suspension")),
        success=lambda obj: (
            f"{obj.number} recorded as blocked."
            + (f" Linked to suspension {obj.suspension.number}." if obj.suspension_id else
               " Raise a vendor suspension to put the block into force.")),
        refuse=lambda obj: (
            _refuse_terminal(obj, "blocked") if obj.is_terminal else
            f"{obj.number} cannot be blocked from its current state."),
        resolve_extra=resolve_suspension,
    )


# -- the re-screening board ---------------------------------------------------------------------------

def _due_on(screening):
    """When a cleared screening falls due for a re-screen.

    ``next_rescreen_on`` when it was set, otherwise the default window off the screening date.
    The plan states those as two rules; they are one rule with a fallback, and unifying them is
    what keeps the board and the register's ``rescreen_due`` card from drifting apart.
    """
    if screening.next_rescreen_on:
        return screening.next_rescreen_on
    if screening.screened_on:
        return screening.screened_on + timedelta(days=ComplianceScreening.DEFAULT_RESCREEN_DAYS)
    return None


@login_required
def screening_rescreen_board(request):
    """Which suppliers are due — or overdue — a re-screen, and which were never screened at all.

    Two queries and no stored "due" flag: the supplier list, then the latest CLEARED screening
    per supplier — narrowed to 7 columns and streamed, because that second read follows the
    append-only ledger and only ~one row per supplier survives the ``setdefault()``. Rows are
    built only for suppliers that need attention, so the page's length tracks the size of the
    PROBLEM rather than the size of the vendor master.
    """
    guard = _need_tenant(request, "review the re-screening board")
    if guard is not None:
        return guard

    today = timezone.localdate()
    soon = today + timedelta(days=RESCREEN_DUE_SOON_DAYS)
    parties = list(_screenable_parties(request.tenant))
    party_ids = [party.pk for party in parties]

    # The most recent CLEARED screening per supplier. Ordered newest-first within each party, so
    # the first row setdefault() sees is the one that counts.
    #
    # Three deliberate narrowings, because screenings are an append-only ledger that grows forever
    # while the supplier list does not — only ~one row per supplier survives ``setdefault()``:
    #  * ``party_id__in=party_ids`` sends pks rather than ``party__in=parties``, which hands Django
    #    model INSTANCES and makes it inline every pk into the ``IN (...)`` SQL text;
    #  * ``.only(...)`` fetches the 7 columns the board and ``rescreening_due.html`` read, not the
    #    26-column row with its three TextFields (``notes``/``decision_note``/
    #    ``threshold_rationale``);
    #  * ``.iterator()`` keeps the rows that lose to ``setdefault()`` out of ``_result_cache``.
    # No ``select_related("party")``: the row-dict takes its Party from ``parties`` above, and the
    # template never touches ``screening.party``, so the join would be pure waste.
    latest = {}
    for screening in (ComplianceScreening.objects
                      .filter(tenant=request.tenant, status="cleared", party_id__in=party_ids)
                      .only("party_id", "screened_on", "next_rescreen_on", "list_source",
                            "number", "status", "tenant_id")
                      .order_by("party_id", "-screened_on", "-id")
                      .iterator(chunk_size=2000)):
        latest.setdefault(screening.party_id, screening)

    rows, overdue, due_soon = [], 0, 0
    for party in parties:
        screening = latest.get(party.pk)
        due = _due_on(screening) if screening is not None else None

        if screening is None:
            # Never cleared. Past due by definition — it sorts to the top of the board.
            state, label, css, sort_on = "never", "Never screened", "badge-red", date.min
            overdue += 1
        elif due is not None and due <= today:
            state, label, css, sort_on = "overdue", "Overdue", "badge-red", due
            overdue += 1
        elif due is not None and due <= soon:
            state, label, css, sort_on = "due_soon", "Due soon", "badge-amber", due
            due_soon += 1
        else:
            continue  # comfortably in date — not this board's business

        rows.append({
            "party": party,
            "screening": screening,
            "due_on": due,
            "days": (today - due).days if due is not None else None,
            "state": state,
            "state_label": label,
            "state_css": css,
            "sort_on": sort_on,
        })

    # Worst first: never-screened, then the most overdue, then what is merely approaching.
    rows.sort(key=lambda row: row["sort_on"])

    return render(request, TEMPLATE_RESCREEN, {
        "rows": rows,
        # ``total`` is every supplier the board SCANNED, so the two attention numbers can be read
        # against the size of the vendor master rather than against each other.
        "stats": {"overdue": overdue, "due_soon": due_soon, "total": len(parties)},
        "today": today,
        "is_admin": _is_admin(request),
    })
