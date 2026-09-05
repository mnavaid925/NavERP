"""Procurement 6.17 Risk & Compliance Management — the policy-acknowledgment READ surfaces.

**NavERP.md bullet 5, "Policy Management & Acknowledgment."** Five routes, and between them they
answer the only four questions an acknowledgement programme ever gets asked: *which policies need
signing off*, *who has signed this one*, *what do I personally still owe*, and *who is late*. The
fifth route is the one verb this module owns.

---

**THE OWNERSHIP CALL — why there is no policy AUTHORING here** (contract §6a). 6.19 Document &
Knowledge Management owns ``procurement.ProcurementPolicy`` [PPOL-]: the table, the version chain,
the publish and archive verbs, and the ``ppolicy_*`` register. 6.17 owns the **acknowledgement
ledger** and nothing else. So this module:

* declares no policy model and edits no file under ``DocumentKnowledgeManagement/``;
* builds **no** ``policy_create`` / ``_edit`` / ``_delete`` / ``_publish`` / ``_archive`` — every
  page here LINKS to 6.19's ``ppolicy_*`` routes for those;
* reads the policy table strictly read-only. The one write any view here makes to a 6.19 row is
  ``write_audit_log`` — an audit entry ABOUT the policy, never a column on it.

:func:`policy_list` is therefore not a second policy register competing with ``ppolicy_list``. It
is the same table asked a different question: 6.19's register asks *what does the rule say*, this
one asks *has anybody signed it*, and every row carries its roster counts rather than its
thresholds.

**``policy_raise_attestations`` is the inversion that keeps 6.19 untouched.** In a single-owner
design, publishing a policy would raise the roster. Publishing belongs to 6.19, and hooking into
it would mean editing their code — so the roster raise is a separate, 6.17-owned, admin-gated,
**idempotent** verb pressed against an ALREADY-published policy. Because it is idempotent it is
also the repair button for somebody who joined the department after the policy went out, which
makes it a better design than the hook would have been rather than a workaround for its absence.

---

**Two rules this module exists to enforce, both of which have shipped as real bugs elsewhere:**

1. **:func:`policy_mine` is a STAFF page reached from the sidebar (L32).** It renders 200 for any
   ordinary logged-in tenant user and never redirects one away — no admin gate, no tenant-guard
   redirect, not even for the tenant-less superuser, who gets an empty roster and a sentence
   explaining why rather than a bounce to the dashboard. A page that answers "what do *I* owe"
   cannot be a page only administrators can open.
2. **``requires_acknowledgment`` (6.19's flag) genuinely governs the ledger.** The refusal lives in
   ``raise_attestations()`` in the model, so a policy with the flag off raises no rows through this
   verb, through a hand-crafted POST, or through the shell. A flag the ledger ignored would be
   decorative, and 6.19's help text promises the opposite.

**Query shape.** :func:`policy_list` annotates the roster counts in the SAME query that lists the
policies — four conditional aggregates over one LEFT JOIN, so a page of 15 policies is a fixed
query count rather than 15 extra roster counts. :func:`policy_detail` select_relateds every hop the
roster rows walk (``user``, ``exempted_by``, ``alert``) and takes its coverage numbers from one
aggregate rather than from ``len()`` of the rendered slice — the slice is capped, the numbers are
not, and they must stay true.

**Context contracts pinned by ``.claude/tasks/contract-procurement-6.17.md`` §1** — repeated on
each view, with the ROW-DICT keys spelled out (L41 §1) for every context key whose value is a list
of dicts. A row-dict key the template misspells renders an em-dash, returns 200, and passes every
status-code test; it is the single most common defect in this codebase, so the keys are frozen in
the docstring beside the code that builds them.
"""
from datetime import timedelta

from django.db.models import Case, Count, F, IntegerField, Q, When
from django.urls import NoReverseMatch, reverse

from apps.core.crud import as_db_int
# 6.19 OWNS this model (contract §6a) and it IS re-exported from apps.procurement.models — but the
# module-direct import is the house rule inside these sub-packages, and 6.19's *_CHOICES tuples are
# deliberately not hoisted into the package __init__, so one line reaches everything needed.
from apps.procurement.models.DocumentKnowledgeManagement.Policies import (
    POLICY_TYPE_CHOICES, STATUS_CHOICES as POLICY_STATUS_CHOICES, ProcurementPolicy)
# NOT-YET-WIRED entity of this SAME sub-module: import the entity MODULE directly, never
# ``from apps.procurement.models import X`` — the sub-package is not wired until the Integrator
# lands it, and a package-level re-export would be a star-import cycle at URLconf import time.
from apps.procurement.models.RiskComplianceManagement.Policies import (
    ATTESTABLE_POLICY_STATUS, DEFAULT_ATTESTATION_DUE_DAYS, DUE_SOON_DAYS, PENDING_STATUS,
    SERIOUSLY_LATE_DAYS, PolicyAttestation, raise_attestations)
from apps.procurement.views._common import *  # noqa: F401,F403

TEMPLATE_LIST = "procurement/riskcompliance/policy/list.html"
TEMPLATE_DETAIL = "procurement/riskcompliance/policy/detail.html"
TEMPLATE_MINE = "procurement/riskcompliance/my_policies.html"
TEMPLATE_OVERDUE = "procurement/riskcompliance/policy_overdue.html"

#: How many roster rows the detail page prints. The COVERAGE NUMBERS beside the table come from an
#: aggregate over the whole roster, never from this slice — so capping the table shortens the page
#: without making a single number on it untrue, and the page links to the filtered register for the
#: rest. ``MAX_ROSTER_SIZE`` is 2000; rendering that inline would be a page nobody can read.
ROSTER_ROW_CAP = 100

#: How many direct successors the detail page names. One hop, bounded — the same discipline 6.19's
#: own detail page applies to the version chain.
SUPERSEDED_BY_CAP = 10

#: How many rows the overdue board prints, worst first. Its STAT TILES are counted over the whole
#: workspace, so the cap shortens the table without changing the numbers above it.
BOARD_ROW_CAP = 200

#: Ceiling on one press of the chase button, so a workspace with a very large overdue backlog
#: cannot mint an unbounded number of inbox items from a single click. Nothing is silently dropped:
#: the page says how many were chased and that pressing it again picks up where it left off (which
#: is safe, because ``raise_chase_alert`` is idempotent per person per policy).
MAX_CHASE_PER_RUN = 200

#: Widest ``due_days`` override the raise form will accept. Beyond a year a "deadline" is not one.
MAX_DUE_DAYS = 365


# -- shared helpers ------------------------------------------------------------------------------

def _is_admin(request):
    """Mirrors ``@tenant_admin_required`` exactly, so a hidden button and a refused POST agree."""
    return bool(request.user.is_superuser or getattr(request.user, "is_tenant_admin", False))


def _need_tenant(request, what):
    """The superuser has no workspace by design; say so instead of rendering an empty page.

    Deliberately NOT used by :func:`policy_mine` — see that view's docstring (L32).
    """
    if request.tenant is None:
        messages.error(request, f"Select a tenant workspace to {what}.")
        return redirect("dashboard:home")
    return None


def _attestation_link(pk):
    """The internal path a chase alert points at, built by the CALLER as the model requires.

    ``ProcurementAlert.clean()`` demands a single-slash internal path — an absolute or
    scheme-relative value would turn the alert card into an open redirect. ``reverse()`` is wrapped
    because this sub-module's URLconf is not spliced into ``apps/procurement/urls/__init__.py``
    until the Integrate step, so during the build the reverse fails and the literal is what a
    resolved route will be anyway.
    """
    try:
        return reverse("procurement:policyattestation_detail", args=[pk])
    except NoReverseMatch:
        return f"/procurement/policy-attestations/{pk}/"


def _policy_qs(request):
    """The acknowledgment register's base queryset, roster counts annotated in the SAME query.

    ANNOTATION CONTRACT — the list template reads exactly these four names off each row, and they
    are annotations rather than model fields, so they exist only on a queryset built here:

    * ``roster_size``  — attestation rows raised for this policy (0 = no roster yet)
    * ``signed_count`` — rows acknowledged by their own owner
    * ``exempt_count`` — rows an administrator excused
    * ``pending_count`` — rows still owed

    Four conditional aggregates over ONE left join, so a page of 15 policies costs the same number
    of queries as a page of one. No percentage is annotated: integer division in SQL would round
    differently per backend, and "12 of 30 signed" reads better than "40%" anyway.

    The ``order_by`` is NOT redundant with ``ProcurementPolicy.Meta.ordering``, which says the same
    thing. Django DROPS the model's default ordering on an aggregate query — the ordering columns
    would otherwise have to join the GROUP BY — so the annotated queryset above arrives at the
    paginator UNORDERED, and MySQL is then free to return rows in a different order per page. The
    visible symptom is a policy repeating on page 2 or vanishing entirely, which no status-code
    check can see. ``-id`` makes the order TOTAL so equal ``created_at`` values cannot tie.
    """
    return (ProcurementPolicy.objects.filter(tenant=request.tenant)
            .select_related("applies_to", "owner")
            .annotate(
                roster_size=Count("attestations", distinct=True),
                signed_count=Count("attestations", distinct=True,
                                   filter=Q(attestations__status="acknowledged")),
                exempt_count=Count("attestations", distinct=True,
                                   filter=Q(attestations__status="exempt")),
                pending_count=Count("attestations", distinct=True,
                                    filter=Q(attestations__status=PENDING_STATUS)),
            )
            .order_by("-created_at", "-id"))


def _org_units(tenant):
    """The scope filter's options — this workspace's org units, ordered by name."""
    from apps.core.models import OrgUnit

    if tenant is None:
        return OrgUnit.objects.none()
    return OrgUnit.objects.filter(tenant=tenant).order_by("name")


def _policy_stats(tenant):
    """The three register tiles, counted over the WHOLE workspace rather than the filtered page.

    A stat card answers "how much acknowledgement work is outstanding?", which must not change
    because somebody typed a search.

    ``attestation_due`` is the only one that needs explaining: it counts the **published policies
    that require acknowledgment and are not settled** — either no roster has been raised for them
    at all, or somebody on it still owes a signature. That is precisely the set of policies the
    raise button and the overdue board exist for, and it is deliberately NOT "policies with a
    pending row", which would silently exclude the worst case of all: a published policy nobody
    has ever been asked to sign.
    """
    if tenant is None:
        return {"published": 0, "draft": 0, "attestation_due": 0}

    base = ProcurementPolicy.objects.filter(tenant=tenant)
    counts = base.aggregate(
        published=Count("pk", filter=Q(status=ATTESTABLE_POLICY_STATUS)),
        draft=Count("pk", filter=Q(status="draft")),
    )
    outstanding = (base
                   .filter(status=ATTESTABLE_POLICY_STATUS, requires_acknowledgment=True)
                   .annotate(_rostered=Count("attestations", distinct=True),
                             _pending=Count("attestations", distinct=True,
                                            filter=Q(attestations__status=PENDING_STATUS)))
                   .filter(Q(_pending__gt=0) | Q(_rostered=0))
                   .count())
    return {"published": counts["published"] or 0,
            "draft": counts["draft"] or 0,
            "attestation_due": outstanding}


def _row_state(attestation, today, soon):
    """One attestation's board state as ``(state, label, css)``.

    ONE definition, shared by :func:`policy_mine` and :func:`policy_overdue_board`, so the badge a
    person sees on their own page and the badge an administrator sees on the chase board can never
    disagree about the same row. ``css`` is a real theme.css class (L33) — theme.css ships only
    badge-green / badge-red / badge-amber / badge-info / badge-muted / badge-slate, and a semantic
    ``badge-success`` renders completely unstyled while passing every test.
    """
    if attestation.status == "acknowledged":
        return "signed", "Signed", "badge-green"
    if attestation.status == "exempt":
        return "exempt", "Exempt", "badge-muted"
    due = attestation.due_on
    if due is None:
        return "open", "No deadline", "badge-slate"
    if due < today:
        late = (today - due).days
        if late >= SERIOUSLY_LATE_DAYS:
            return "overdue", "Seriously overdue", "badge-red"
        return "overdue", "Overdue", "badge-red"
    if due <= soon:
        return "due_soon", "Due soon", "badge-amber"
    return "open", "Open", "badge-info"


# -- the acknowledgment register -----------------------------------------------------------------

@login_required
def policy_list(request):
    """Every policy in the workspace, seen through its sign-off coverage.

    CONTEXT (crud_list's ``object_list`` / ``page_obj`` / ``q``, plus)::

        category_choices  6.19's POLICY_TYPE_CHOICES, under the KEY the contract pins
        status_choices    6.19's policy STATUS_CHOICES (draft / published / archived)
        org_units         this workspace's org units, for the scope filter
        stats             {published, draft, attestation_due}
        is_admin          gates the raise button, mirroring @tenant_admin_required

    Each row additionally carries the four annotations documented on :func:`_policy_qs`.

    The filter tuple is exactly ``category`` / ``status`` / ``org_unit``, so the bar offers exactly
    those three plus ``q`` — no dead ``<select>`` posting a parameter the view ignores. The two
    enum filters are validated against the model's own CHOICES before they narrow, and the org-unit
    filter goes through ``as_db_int``, so neither a stale bookmark nor a hand-edited query string
    can silently empty the register or 500 it (L11).

    ``category`` is the GET parameter and ``policy_type`` is the column: the contract pins the
    context key as ``category_choices``, and the parameter is named to match what the page calls
    it rather than what 6.19 calls the column.
    """
    guard = _need_tenant(request, "review policy acknowledgments")
    if guard is not None:
        return guard
    return crud_list(
        request,
        _policy_qs(request),
        TEMPLATE_LIST,
        # The rule as written is searchable: people look for "three quotes", not for PPOL-00007.
        search_fields=["number", "title", "summary", "body"],
        filters=[("category", "policy_type", False),
                 ("status", "status", False),
                 ("org_unit", "applies_to_id", True)],
        extra_context={
            "category_choices": POLICY_TYPE_CHOICES,
            "status_choices": POLICY_STATUS_CHOICES,
            "org_units": _org_units(request.tenant),
            "stats": _policy_stats(request.tenant),
            "is_admin": _is_admin(request),
        },
    )


@login_required
def policy_detail(request, pk):
    """One policy, its roster, and how much of that roster has actually signed.

    CONTEXT::

        obj                the ProcurementPolicy (6.19's row, read-only here)
        attestations       up to ROSTER_ROW_CAP roster rows, outstanding first
        attestation_stats  {target, attested, outstanding, rate}
        supersedes         the version this one replaces, or None (ONE hop)
        superseded_by      up to SUPERSEDED_BY_CAP direct successors (ONE hop)
        allowed_actions    row-dicts — see below
        is_admin           mirrors @tenant_admin_required

    ROW-DICT CONTRACT (L41 §1) — every entry of ``allowed_actions`` carries EXACTLY::

        {"key":     str,   # stable identifier; the template branches on it
         "label":   str,   # button caption
         "icon":    str,   # lucide icon name
         "css":     str,   # a btn-* class
         "help":    str,   # the sentence printed under the button
         "confirm": str}   # the confirm() text — NO apostrophes (L42), NO user-typed value

    ``attestation_stats.rate`` is the percentage of the roster that has **signed**, and exemptions
    are deliberately not counted into it: an exemption is a decision to stop asking somebody, not a
    signature, and rolling the two together would let a workspace reach 100% coverage without a
    single person reading the policy. The page says so in as many words.

    Every number in ``attestation_stats`` comes from an aggregate over the WHOLE roster, never from
    ``len(attestations)`` — the table is capped and the numbers are not.

    ``allowed_actions`` is empty unless the user is a tenant administrator AND the policy is
    published AND it requires acknowledgment, which is exactly when
    :func:`policy_raise_attestations` would refuse — a hidden button and a refused POST always
    agree. It stays offered once the roster is complete, because raising it again is the repair
    button for somebody who joined afterwards and creates nothing when there is nothing to create.
    """
    guard = _need_tenant(request, "review policy acknowledgments")
    if guard is not None:
        return guard

    obj = get_object_or_404(
        ProcurementPolicy.objects.filter(tenant=request.tenant)
        .select_related("applies_to", "owner", "previous_version", "threshold_currency"), pk=pk)

    roster = PolicyAttestation.objects.filter(tenant=request.tenant, policy=obj)
    stats = roster.aggregate(
        target=Count("id"),
        attested=Count("id", filter=Q(status="acknowledged")),
        outstanding=Count("id", filter=Q(status=PENDING_STATUS)),
    )
    target = stats["target"] or 0
    attested = stats["attested"] or 0
    attestation_stats = {
        "target": target,
        "attested": attested,
        "outstanding": stats["outstanding"] or 0,
        # Integer percent, computed in Python so every backend agrees on the rounding. 0 rather
        # than a division error when nobody has been asked yet — and the page distinguishes "0% of
        # nobody" from "0% of thirty people", because those are very different facts.
        "rate": int(round(100.0 * attested / target)) if target else 0,
    }

    # Outstanding first, then the earliest deadline, then by name. The Case annotation is what puts
    # pending rows at the top: "pending" sorts LAST alphabetically, so ordering on the raw column
    # would bury exactly the rows this page exists to show.
    attestations = list(
        roster.select_related("user", "exempted_by", "alert")
        .annotate(_settle_order=Case(When(status=PENDING_STATUS, then=0), default=1,
                                     output_field=IntegerField()))
        .order_by("_settle_order", F("due_on").asc(nulls_last=True),
                  "user__first_name", "user__last_name", "user__username", "id")[:ROSTER_ROW_CAP])

    is_admin = _is_admin(request)
    allowed_actions = []
    if is_admin and obj.status == ATTESTABLE_POLICY_STATUS and obj.requires_acknowledgment:
        allowed_actions.append({
            "key": "raise_attestations",
            "label": "Raise attestations",
            "icon": "user-check",
            "css": "btn-primary",
            "help": ("Assigns this policy to everybody it applies to who does not already have it. "
                     "Safe to press again at any time: it creates nothing for people who are "
                     "already on the roster, moves no deadline anybody is working to, and cannot "
                     "disturb a signature already on file."),
            # Only the SYSTEM-ASSIGNED number reaches a confirm() string — never the title, which
            # is staff-typed (L42). No apostrophes: an escaped &#39; is decoded back to a bare
            # quote by the HTML parser, the handler throws, and the form then submits with NO
            # confirmation at all.
            "confirm": (f"Raise policy attestations for {obj.number}? Everybody this policy "
                        f"applies to will be asked to sign it off."),
        })

    return render(request, TEMPLATE_DETAIL, {
        "obj": obj,
        "attestations": attestations,
        "attestation_stats": attestation_stats,
        "supersedes": obj.previous_version,
        "superseded_by": list(obj.superseded_by.all()[:SUPERSEDED_BY_CAP]),
        "allowed_actions": allowed_actions,
        "is_admin": is_admin,
    })


# -- the staff page ------------------------------------------------------------------------------

@login_required
def policy_mine(request):
    """What **I** personally still owe, and what I have already signed.

    CONTEXT::

        rows   row-dicts — see below
        stats  {pending, overdue, signed}
        today  the date every deadline on the page is measured against

    ROW-DICT CONTRACT (L41 §1) — every entry of ``rows`` carries EXACTLY::

        {"attestation": PolicyAttestation,   # the row itself; the template reads .acknowledged_at,
                                             #   .exempt_reason, .exempted_by, .pk through it
         "policy":      ProcurementPolicy,   # .number, .title, .version_number, .summary
         "due_on":      date | None,
         "days_late":   int | None,          # negative while still ahead; None with no deadline
         "state":       str,                 # signed | exempt | overdue | due_soon | open
         "state_label": str,
         "state_css":   str,                 # a real theme.css badge class
         "can_sign":    bool,                # always the owner here, so this is just "is pending"
         "sort_on":     tuple}               # the view's own ordering key; not rendered

    **STAFF-FACING, AND THAT IS A HARD REQUIREMENT (L32).** This page is reached from the sidebar
    by ordinary people who have policies to sign. It carries no admin gate and — uniquely in this
    module — no ``_need_tenant`` redirect either: a tenant-less user gets an empty roster and a
    sentence saying why, because bouncing somebody off the page that answers "what do I owe" is
    indistinguishable from telling them they owe nothing. It renders 200 for every logged-in user,
    always.

    ``stats.pending`` counts everything still owed INCLUDING the overdue rows, and ``stats.overdue``
    is the subset of those past their date — they are deliberately not disjoint, because "you owe
    four things, two of them late" is the sentence a person needs, and two tiles that had to be
    added together to get the total would be the wrong pair of numbers.

    The roster is not paginated. It is one person's own obligations, bounded in practice by the
    number of policies a workspace publishes; a page of somebody's own homework that needed paging
    would be a different problem than pagination.
    """
    today = timezone.localdate()
    soon = today + timedelta(days=DUE_SOON_DAYS)
    rows, pending, overdue, signed = [], 0, 0, 0

    if request.tenant is not None:
        roster = (PolicyAttestation.objects
                  .filter(tenant=request.tenant, user=request.user)
                  .select_related("policy", "exempted_by"))
        for attestation in roster:
            state, label, css = _row_state(attestation, today, soon)
            if state == "signed":
                signed += 1
            elif attestation.is_pending:
                pending += 1
                if state == "overdue":
                    overdue += 1
            rows.append({
                "attestation": attestation,
                "policy": attestation.policy,
                "due_on": attestation.due_on,
                "days_late": attestation.days_late,
                "state": state,
                "state_label": label,
                "state_css": css,
                "can_sign": attestation.is_pending,
                # Outstanding first, latest first within that, then the earliest deadline. A row
                # with no deadline sorts behind the dated ones rather than ahead of them, which is
                # what the huge sentinel is for.
                "sort_on": (0 if attestation.is_pending else 1,
                            -(attestation.days_late if attestation.days_late is not None else -99999),
                            attestation.pk),
            })

    rows.sort(key=lambda row: row["sort_on"])
    return render(request, TEMPLATE_MINE, {
        "rows": rows,
        "stats": {"pending": pending, "overdue": overdue, "signed": signed},
        "today": today,
    })


# -- the chase board -----------------------------------------------------------------------------

@login_required
def policy_overdue_board(request):
    """Who is late, how late, and — on POST — one inbox item each to say so.

    CONTEXT::

        rows      row-dicts — see below
        stats     {overdue, due_soon}
        today     the date every deadline on the page is measured against
        is_admin  gates the chase button, mirroring what the POST leg itself checks

    ROW-DICT CONTRACT (L41 §1) — every entry of ``rows`` carries EXACTLY::

        {"attestation": PolicyAttestation,   # .pk, .alert, .status read through it
         "policy":      ProcurementPolicy,   # .number, .title, .version_number, .pk
         "user":        User,                # who owes the signature
         "due_on":      date,                # never None — an undated row is not late
         "days_late":   int,                 # negative while still ahead (a due_soon row)
         "state":       str,                 # overdue | due_soon
         "state_label": str,
         "state_css":   str,                 # a real theme.css badge class
         "chased":      bool,                # an alert has already been raised for this row
         "sort_on":     tuple}               # the view's own ordering key; not rendered

    **GET writes nothing and is open to any logged-in member of the workspace; only the POST leg is
    administrator-gated, inside the view.** That is the same shape ``fraud_scan`` next door uses,
    and it is deliberate: seeing who is late is ordinary compliance work, while sending everybody
    on the list an inbox item is not, and splitting them across two routes would give the read-only
    page an admin gate it does not need.

    The POST leg raises ONE ``ProcurementAlert`` per overdue row through
    ``PolicyAttestation.raise_chase_alert``, which is idempotent per person per policy: it refuses
    a row that is not overdue, one that already stamped an alert, and one where an OPEN alert is
    already chasing the same person about the same policy. So pressing the button weekly produces
    one inbox item per person per policy, not one per press — which is what makes a chase button
    usable at all.

    Nothing else is written. No status moves, no deadline shifts, no signature is applied, and no
    row on 6.19's policy table is touched.
    """
    guard = _need_tenant(request, "review the policy chase board")
    if guard is not None:
        return guard

    today = timezone.localdate()
    soon = today + timedelta(days=DUE_SOON_DAYS)
    is_admin = _is_admin(request)

    # Every row this board is about: still owed, has a deadline, and that deadline is either past
    # or inside the "due soon" window. Ordered worst-first so both the cap and the chase run take
    # the most overdue rows rather than an arbitrary slice.
    board_qs = (PolicyAttestation.objects
                .filter(tenant=request.tenant, status=PENDING_STATUS,
                        due_on__isnull=False, due_on__lte=soon)
                .select_related("policy", "user", "alert")
                .order_by("due_on", "id"))

    if request.method == "POST":
        if not is_admin:
            messages.error(request, "Only a workspace administrator can chase policy sign-offs.")
            return redirect("procurement:policy_overdue_board")

        raised = 0
        considered = 0
        # list() FIRST: the loop body saves each row, and iterating a sliced queryset lazily while
        # writing to the rows it is walking is how a chase run silently skips people.
        for attestation in list(board_qs.filter(due_on__lt=today)[:MAX_CHASE_PER_RUN]):
            considered += 1
            alert = attestation.raise_chase_alert(
                request.user, link_url=_attestation_link(attestation.pk))
            if alert is not None:
                raised += 1
                write_audit_log(request.user, attestation, "update",
                                {"chase_alert": alert.pk, "policy": attestation.policy.number})

        if raised:
            messages.success(
                request,
                f"Raised {raised} chase alert(s) in the Task and Alert Center, out of "
                f"{considered} overdue sign-off(s) looked at. The rest were already being chased.")
        elif considered:
            messages.info(
                request,
                f"All {considered} overdue sign-off(s) are already being chased - nothing new to "
                f"raise. Pressing this again never sends anybody a second copy.")
        else:
            messages.info(request, "Nothing is overdue right now, so there is nobody to chase.")
        return redirect("procurement:policy_overdue_board")

    # Counted over the whole workspace, so the tiles keep meaning something above a capped table.
    stats = (PolicyAttestation.objects
             .filter(tenant=request.tenant, status=PENDING_STATUS, due_on__isnull=False)
             .aggregate(overdue=Count("id", filter=Q(due_on__lt=today)),
                        due_soon=Count("id", filter=Q(due_on__gte=today, due_on__lte=soon))))

    rows = []
    for attestation in board_qs[:BOARD_ROW_CAP]:
        state, label, css = _row_state(attestation, today, soon)
        rows.append({
            "attestation": attestation,
            "policy": attestation.policy,
            "user": attestation.user,
            "due_on": attestation.due_on,
            "days_late": attestation.days_late,
            "state": state,
            "state_label": label,
            "state_css": css,
            "chased": attestation.alert_id is not None,
            "sort_on": (attestation.due_on, attestation.pk),
        })

    return render(request, TEMPLATE_OVERDUE, {
        "rows": rows,
        "stats": {"overdue": stats["overdue"] or 0, "due_soon": stats["due_soon"] or 0},
        "today": today,
        "is_admin": is_admin,
    })


# -- the one verb this module owns ---------------------------------------------------------------

@login_required
@tenant_admin_required
@require_POST
def policy_raise_attestations(request, pk):
    """Raise (or repair) the sign-off roster for one already-published policy.

    **The 6.17-owned inversion of "publishing raises the roster"** (contract §6a). Publishing
    belongs to 6.19; hooking into it would mean editing their code, so this is a separate verb an
    administrator presses against a policy that is ALREADY published — and because it is idempotent
    it doubles as the repair button for somebody who joined the department after the policy went
    out. Zero edits to 6.19.

    Every rule lives in ``raise_attestations()`` on the model, so a hand-crafted POST is refused
    exactly as a click is. It returns a SENTENCE rather than a silent zero for each of its three
    refusals — not published, ``requires_acknowledgment`` off, empty or oversized audience —
    because a verb that quietly does nothing is indistinguishable from a broken one.

    The optional ``due_days`` override arrives from a POST body, so it is validated the way every
    other posted number in this app is (L11): ``as_db_int`` refuses junk, superscripts and
    over-range values, and anything outside 0..MAX_DUE_DAYS is reported and ignored rather than
    raising. An absent or refused value falls through to the module default of
    DEFAULT_ATTESTATION_DUE_DAYS days.
    """
    policy = get_object_or_404(ProcurementPolicy.objects.filter(tenant=request.tenant), pk=pk)

    raw_days = (request.POST.get("due_days") or "").strip()
    due_days = None
    if raw_days:
        parsed = as_db_int(raw_days)
        if parsed is None or parsed > MAX_DUE_DAYS:
            messages.warning(
                request,
                f"That sign-off window was not a whole number of days between 0 and "
                f"{MAX_DUE_DAYS}, so the standard {DEFAULT_ATTESTATION_DUE_DAYS}-day window was "
                f"used instead.")
        else:
            due_days = parsed

    result = raise_attestations(policy, user=request.user, due_days=due_days)

    if result.refusal:
        messages.error(request, result.refusal)
        return redirect("procurement:policy_detail", pk=pk)

    write_audit_log(request.user, policy, "update", {
        "action": "raise_attestations",
        "created": result.created,
        "already_on_roster": result.existing,
        "audience": result.audience,
        "due_days": DEFAULT_ATTESTATION_DUE_DAYS if due_days is None else due_days,
    })

    if result.created:
        messages.success(
            request,
            f"Raised {result.created} attestation(s) for {policy.number}. "
            f"{result.existing} person(s) were already on the roster and were left exactly as "
            f"they were.")
    else:
        messages.info(
            request,
            f"Everybody {policy.number} applies to is already on its roster - "
            f"{result.existing} person(s), nothing created, no deadline moved and no signature "
            f"touched.")
    return redirect("procurement:policy_detail", pk=pk)
