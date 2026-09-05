"""Procurement 6.17 Risk & Compliance Management — PolicyAttestation CRUD and the two verbs.

Seven routes: the ledger register, one detail page, assign/amend/withdraw, and the two verbs that
are the whole point of the sub-module — :func:`attestation_sign` and :func:`attestation_exempt`.

---

**THE ONE RULE THIS FILE EXISTS TO ENFORCE: only the owner may sign.**

:func:`attestation_sign` refuses every user that is not the attestation's own ``user`` — **a tenant
administrator included, a superuser included.** There is no override, no "on behalf of" parameter
and no admin escape hatch, and that is not an oversight to be tidied up later: a signature an
administrator can apply for somebody else records nothing anybody would testify to, and the ledger
would then hold a column of assertions about people who never read the policy. The guard is checked
here AND again inside ``PolicyAttestation.acknowledge()``, so a hand-crafted POST is refused exactly
as a click is.

The honest administrative answer to "this person should not have to sign" already exists and it is
a **different verb with a different word on it**: :func:`attestation_exempt`, which is
administrator-gated, demands a written reason, and stamps who granted it and when. An exemption is
visible as an exemption everywhere it appears and is never counted as a signature — including in
``policy_detail``'s coverage rate.

Neither verb has an inverse. There is no un-sign and no un-exempt, because a withdrawn signature is
not a correction; it is a second, contradictory claim about the same day.

---

**Everything else, in the order a reviewer will look for it:**

* **Every queryset is ``filter(tenant=request.tenant)``** — never ``.all()`` — and every object is
  fetched ``get_object_or_404(..., tenant=request.tenant)``, so a cross-tenant id is a 404 rather
  than somebody else's roster row.
* **Assign and amend are ``@login_required``; DELETE and EXEMPT add ``@tenant_admin_required``**
  (with ``@require_POST``, in that order, L27). ``sign`` is gated by OWNERSHIP instead, which is
  strictly narrower than the admin gate and deliberately orthogonal to it.
* **A terminal row is evidence: no edit, no delete, no re-open.** Both are refused with a sentence
  once a row is acknowledged or exempt, and the template hides both buttons at exactly that point —
  a hidden button and a refused POST always agree.
* **Both verbs run the row under ``select_for_update()`` inside ``transaction.atomic()``**, so two
  requests racing on the same row cannot both stamp a state change.
* **Nothing here writes to 6.19's policy table or to the spine** (L29). Signing a policy moves one
  ledger row and writes one audit entry; it publishes nothing, blocks nothing and grants nothing.
  In particular no page or purchase is EVER gated on an attestation — 6.19's own model warns about
  exactly that, and authorising on the strength of a sign-off is a control people believe in.
* **Query shape.** The register select_relateds ``policy`` and ``user`` — a row's own ``__str__``
  walks both, so without the hint a page of 15 rows is 31 queries. The detail page adds
  ``exempted_by`` and ``alert``.

**Context contracts pinned by ``.claude/tasks/contract-procurement-6.17.md`` §1:**

``policyattestation_list``   → crud_list's ``object_list`` / ``page_obj`` / ``q``, plus
                               ``status_choices``, ``policies``, ``users``, ``stats``, ``is_admin``.
``policyattestation_detail`` → ``obj``, ``policy``, ``can_sign``, ``allowed_actions``, ``is_admin``.
``policyattestation_create`` / ``_edit`` → nothing beyond the ``crud_*`` keys.
"""
from django.db import transaction
from django.db.models import Count, Q

from apps.core.crud import _changed
from apps.procurement.forms.RiskComplianceManagement.Policies import PolicyAttestationForm
# 6.19 OWNS this model (contract §6a) — read-only from here, never edited, never re-declared.
from apps.procurement.models.DocumentKnowledgeManagement.Policies import ProcurementPolicy
# NOT-YET-WIRED entity of this SAME sub-module: import the entity MODULE directly, never
# ``from apps.procurement.models import X`` — the sub-package is not wired until the Integrator
# lands it, and a package-level re-export would be a star-import cycle at URLconf import time.
from apps.procurement.models.RiskComplianceManagement.Policies import (
    PENDING_STATUS, STATUS_CHOICES, PolicyAttestation)
from apps.procurement.views._common import *  # noqa: F401,F403

TEMPLATE_LIST = "procurement/riskcompliance/attestation/list.html"
TEMPLATE_DETAIL = "procurement/riskcompliance/attestation/detail.html"
TEMPLATE_FORM = "procurement/riskcompliance/attestation/form.html"

#: Every hop a register row (or its own ``__str__``) walks.
_ROW_RELATIONS = ("policy", "user")

#: Every hop the detail page walks.
_DETAIL_RELATIONS = _ROW_RELATIONS + ("exempted_by", "alert", "policy__applies_to", "policy__owner")

#: Longest exemption reason accepted from a POST. The column is 255 and ``mark_exempt`` slices to
#: it; refusing a longer one here means the person is told their sentence was too long instead of
#: silently having it cut in half.
MAX_REASON_LENGTH = 255

#: Longest acknowledgement note accepted from a POST. The column is a TextField, so this is a
#: sanity ceiling on a free-text field that arrives from a browser, not a schema limit.
MAX_NOTE_LENGTH = 2000


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


def _attestation_qs(request):
    return (PolicyAttestation.objects.filter(tenant=request.tenant)
            .select_related(*_ROW_RELATIONS))


def _refuse_terminal(obj, verb):
    return (f"That sign-off for {obj.policy.number} has already been "
            f"{obj.get_status_display().lower()} and cannot be {verb}. A settled attestation is "
            f"evidence - if the assignment itself was wrong, record why on the policy rather than "
            f"rewriting the row.")


def _ledger_policies(tenant):
    """The policy filter's options: policies that actually appear in this ledger.

    Deliberately narrower than "every published policy". A filter option that can only ever return
    an empty register is a dead end the page invites people into, and the assignment form next door
    is where the full published list belongs.
    """
    if tenant is None:
        return ProcurementPolicy.objects.none()
    return (ProcurementPolicy.objects
            .filter(tenant=tenant, attestations__isnull=False)
            .distinct().order_by("title", "version_number"))


def _ledger_users(tenant):
    """The person filter's options: people who actually appear in this ledger, same reasoning."""
    from django.contrib.auth import get_user_model

    User = get_user_model()
    if tenant is None:
        return User.objects.none()
    return (User.objects
            .filter(tenant=tenant, procurement_policy_attestations__isnull=False)
            .distinct().order_by("first_name", "last_name", "username"))


def _stats(tenant, today):
    """The three register tiles.

    Counted over the WHOLE workspace, not the filtered page: a stat card answers "how much sign-off
    work is outstanding?", which must not change because somebody typed a search.

    ``pending`` and ``overdue`` are deliberately NOT disjoint — overdue rows are pending rows that
    have run out of time, and two tiles you had to add together to get the total would be the wrong
    pair of numbers to print.
    """
    if tenant is None:
        return {"pending": 0, "overdue": 0, "acknowledged": 0}
    return PolicyAttestation.objects.filter(tenant=tenant).aggregate(
        pending=Count("id", filter=Q(status=PENDING_STATUS)),
        overdue=Count("id", filter=Q(status=PENDING_STATUS, due_on__lt=today)),
        acknowledged=Count("id", filter=Q(status="acknowledged")),
    )


# -- the register --------------------------------------------------------------------------------

@login_required
def policyattestation_list(request):
    """The acknowledgement ledger — every obligation in the workspace, newest first.

    CONTEXT (crud_list's ``object_list`` / ``page_obj`` / ``q``, plus)::

        status_choices  pending / acknowledged / exempt
        policies        policies that appear in this ledger (never a dead filter option)
        users           people who appear in this ledger (same)
        stats           {pending, overdue, acknowledged}
        is_admin        gates the Assign and Withdraw controls

    The filter tuple is exactly ``status`` / ``policy`` / ``user``, so the bar offers exactly those
    three plus ``q`` — no dead ``<select>`` posting a parameter the view ignores. ``status`` is
    validated against the model's own CHOICES before it narrows and the two FK filters go through
    ``as_db_int``, so neither a stale bookmark nor a hand-edited query string can silently empty the
    register or 500 it (L11).
    """
    guard = _need_tenant(request, "review policy sign-offs")
    if guard is not None:
        return guard
    return crud_list(
        request,
        _attestation_qs(request),
        TEMPLATE_LIST,
        # People search for the policy or the person, never for a row id — this ledger has no
        # number of its own, which is exactly why both hops are searchable.
        search_fields=["policy__number", "policy__title", "user__username", "user__first_name",
                       "user__last_name", "user__email"],
        filters=[("status", "status", False),
                 ("policy", "policy_id", True),
                 ("user", "user_id", True)],
        extra_context={
            "status_choices": STATUS_CHOICES,
            "policies": _ledger_policies(request.tenant),
            "users": _ledger_users(request.tenant),
            "stats": _stats(request.tenant, timezone.localdate()),
            "is_admin": _is_admin(request),
        },
    )


@login_required
def policyattestation_detail(request, pk):
    """One person's obligation to one policy, and what became of it.

    CONTEXT::

        obj              the PolicyAttestation
        policy           obj.policy, lifted under the name the contract pins
        can_sign         True only for the row's OWN owner while it is still pending
        allowed_actions  row-dicts — see below
        is_admin         mirrors @tenant_admin_required

    ROW-DICT CONTRACT (L41 §1) — every entry of ``allowed_actions`` carries EXACTLY::

        {"key":              str,   # "sign" | "exempt"; the template branches on it to pick a form
         "label":            str,   # button caption
         "icon":             str,   # lucide icon name
         "css":              str,   # a btn-* class
         "help":             str,   # the sentence printed above the button
         "note_name":        str,   # the POST field name this action reads
         "note_label":       str,   # the label on that field
         "note_placeholder": str,
         "note_required":    bool,  # a reason is required to exempt, optional to sign
         "confirm":          str}   # confirm() text — NO apostrophes (L42), NO user-typed value

    The list holds at most one entry, because the two verbs are gated on mutually exclusive facts:
    ``sign`` needs you to BE the person, ``exempt`` needs you to be an administrator excusing
    somebody. An administrator looking at their own row sees ``sign`` and not ``exempt`` — they can
    sign what they owe, and excusing yourself is not a thing this ledger offers. It is empty
    entirely once the row is settled, which is exactly when both verbs would refuse.
    """
    guard = _need_tenant(request, "review policy sign-offs")
    if guard is not None:
        return guard

    obj = get_object_or_404(
        PolicyAttestation.objects.filter(tenant=request.tenant)
        .select_related(*_DETAIL_RELATIONS), pk=pk)

    is_admin = _is_admin(request)
    # OWNER-ONLY, and the same expression attestation_sign re-checks. Compared on the id rather
    # than on the object so an unfetched user cannot make this quietly True.
    can_sign = bool(obj.is_pending and request.user.is_authenticated
                    and request.user.pk == obj.user_id)

    allowed_actions = []
    if can_sign:
        allowed_actions.append({
            "key": "sign",
            "label": "I have read it - sign it off",
            "icon": "check",
            "css": "btn-primary",
            "help": ("Signing records that YOU have read this policy, on today's date, under your "
                     "own account. Nobody else can do it for you, and it cannot be undone."),
            "note_name": "note",
            "note_label": "Note (optional)",
            "note_placeholder": "Anything you want on the record alongside your sign-off",
            "note_required": False,
            "confirm": (f"Sign off {obj.policy.number}? This records that you have read it, and "
                        f"it cannot be undone."),
        })
    elif is_admin and obj.is_pending:
        allowed_actions.append({
            "key": "exempt",
            "label": "Record an exemption",
            "icon": "user-minus",
            "css": "btn-outline",
            "help": ("An exemption excuses this person from signing and says, on the record, who "
                     "excused them and why. It is NOT a signature: it is never counted as one, and "
                     "the coverage figure on the policy ignores it."),
            "note_name": "reason",
            "note_label": "Reason",
            "note_placeholder": "Why this person is not being asked to sign",
            "note_required": True,
            "confirm": (f"Record an exemption from {obj.policy.number} for this person? It cannot "
                        f"be undone, and your name is stamped on it."),
        })

    return render(request, TEMPLATE_DETAIL, {
        "obj": obj,
        "policy": obj.policy,
        "can_sign": can_sign,
        "allowed_actions": allowed_actions,
        "is_admin": is_admin,
    })


# -- assign / amend / withdraw ---------------------------------------------------------------------

@login_required
def policyattestation_create(request):
    """Assign one published policy to one named person, by hand.

    The single-row companion to ``policy_raise_attestations``, which raises a whole roster. Both
    exist because they answer different questions: the roster raiser puts a policy to everybody it
    applies to, and this puts it to one person a rule did not reach.
    """
    guard = _need_tenant(request, "assign policy sign-offs")
    if guard is not None:
        return guard
    return crud_create(request, form_class=PolicyAttestationForm, template=TEMPLATE_FORM,
                       success_url="procurement:policyattestation_list")


@login_required
@tenant_admin_required
def policyattestation_edit(request, pk):
    """Amend an assignment — refused once it has been signed or exempted.

    Changing who owes a signature that has already been given would rewrite the evidence. The only
    thing worth amending on a live row is the deadline, and that is what the form offers on an
    existing row: ``PolicyAttestationForm`` marks ``policy`` and ``user`` ``disabled`` once
    ``instance.pk`` is set, so Django ignores whatever the POST said about them.

    **Admin-gated**, matching ``policyattestation_delete`` and ``attestation_exempt``. Amending is
    not a lesser verb here: pushing ``due_on`` out takes a row off the overdue board, and moving
    ``user`` transfers the obligation to somebody else — either one is the withdrawal that delete
    exists to restrict to administrators, reached through a different route. The Administration
    card on the detail page has always hidden this button behind ``is_admin``; without the
    decorator that was cosmetic, because the route itself had no gate.
    """
    obj = get_object_or_404(PolicyAttestation.objects.select_related("policy"), pk=pk,
                            tenant=request.tenant)
    if obj.is_terminal:
        messages.error(request, _refuse_terminal(obj, "edited"))
        return redirect("procurement:policyattestation_detail", pk=pk)
    return crud_edit(request, model=PolicyAttestation, pk=pk, form_class=PolicyAttestationForm,
                     template=TEMPLATE_FORM,
                     success_url="procurement:policyattestation_list")


@login_required
@tenant_admin_required
@require_POST
def policyattestation_delete(request, pk):
    """Withdraw an assignment. Admin-gated, and refused once the row has settled.

    Withdrawing a PENDING obligation is a legitimate correction — somebody was assigned a policy
    that does not apply to them. Deleting a SIGNED one destroys the evidence that they read it, so
    it is refused with a sentence rather than gated behind a scarier confirm dialog.
    """
    obj = get_object_or_404(PolicyAttestation.objects.select_related("policy"), pk=pk,
                            tenant=request.tenant)
    if obj.is_terminal:
        messages.error(request, _refuse_terminal(obj, "withdrawn"))
        return redirect("procurement:policyattestation_detail", pk=pk)
    return crud_delete(request, model=PolicyAttestation, pk=pk,
                       success_url="procurement:policyattestation_list")


# -- the two verbs ---------------------------------------------------------------------------------

@login_required
@require_POST
def attestation_sign(request, pk):
    """Sign one attestation off. **OWNER ONLY — an administrator cannot sign for somebody else.**

    Deliberately NOT ``@tenant_admin_required``, and deliberately not gated on it either way: the
    admin flag is irrelevant here in BOTH directions. An ordinary member of staff must be able to
    sign their own row (a sign-off only an administrator could apply would never be given), and an
    administrator must NOT be able to sign anybody else's (a sign-off an administrator could apply
    on your behalf is not evidence that you read anything).

    The ownership check is made twice on purpose — here, so the refusal carries a sentence that
    explains itself, and again inside ``PolicyAttestation.acknowledge()``, which is the guard a
    direct POST, a shell session or a future caller has to get past. Neither is redundant: this one
    is the message, that one is the rule.
    """
    guard = _need_tenant(request, "sign off policies")
    if guard is not None:
        return guard

    note = (request.POST.get("note") or "").strip()[:MAX_NOTE_LENGTH]

    with transaction.atomic():
        obj = get_object_or_404(
            PolicyAttestation.objects.select_for_update().select_related("policy"),
            pk=pk, tenant=request.tenant)

        if request.user.pk != obj.user_id:
            messages.error(
                request,
                "Only the person named on a sign-off can sign it, and that includes "
                "administrators. If they should not have to sign it, record an exemption instead "
                "- that is a different thing, and it says so on the record.")
            return redirect("procurement:policyattestation_detail", pk=pk)

        if not obj.acknowledge(request.user, note):
            messages.error(
                request,
                f"That sign-off for {obj.policy.number} is already "
                f"{obj.get_status_display().lower()} and cannot be signed again.")
            return redirect("procurement:policyattestation_detail", pk=pk)

    write_audit_log(request.user, obj, "update",
                    {"action": "acknowledge", "policy": obj.policy.number,
                     "note": note[:200]})
    messages.success(
        request,
        f"Signed off {obj.policy.number}. Your acknowledgement is on the record against your own "
        f"account, dated today.")
    return redirect("procurement:policyattestation_detail", pk=pk)


@login_required
@tenant_admin_required
@require_POST
def attestation_exempt(request, pk):
    """Excuse one person from signing one policy. Administrator-gated, reason REQUIRED.

    The one legitimate administrative answer to "this person should not have to sign" — and the
    reason it exists is that the alternative, letting an administrator sign on somebody's behalf,
    would empty the ledger of the only thing it holds.

    The reason is not optional and never has been: an exemption is the one way out of a stated
    obligation, so an unexplained one is the first thing an audit asks about and the last thing
    anybody can answer months later. ``mark_exempt`` refuses a blank one on the model too, so a
    hand-crafted POST with no reason is refused exactly as an empty box is.

    An exemption is never counted as a signature anywhere — not in the register tiles, not in the
    coverage rate on the policy page, and not in the word printed on the row.
    """
    guard = _need_tenant(request, "record policy exemptions")
    if guard is not None:
        return guard

    reason = (request.POST.get("reason") or "").strip()
    if not reason:
        messages.error(
            request,
            "Say why this person is being excused. An exemption with no stated reason is the "
            "first thing an audit asks about and the last thing anybody can answer months later.")
        return redirect("procurement:policyattestation_detail", pk=pk)
    if len(reason) > MAX_REASON_LENGTH:
        messages.error(
            request,
            f"That reason is longer than {MAX_REASON_LENGTH} characters. Shorten it rather than "
            f"letting it be cut off half way through a sentence.")
        return redirect("procurement:policyattestation_detail", pk=pk)

    with transaction.atomic():
        obj = get_object_or_404(
            PolicyAttestation.objects.select_for_update().select_related("policy"),
            pk=pk, tenant=request.tenant)

        if not obj.mark_exempt(request.user, reason):
            messages.error(
                request,
                f"That sign-off for {obj.policy.number} is already "
                f"{obj.get_status_display().lower()} and cannot be exempted.")
            return redirect("procurement:policyattestation_detail", pk=pk)

    write_audit_log(request.user, obj, "update",
                    {"action": "exempt", "policy": obj.policy.number, "reason": reason[:200]})
    messages.success(
        request,
        f"Exemption from {obj.policy.number} recorded, with your name on it. It is not counted as "
        f"a signature anywhere.")
    return redirect("procurement:policyattestation_detail", pk=pk)
