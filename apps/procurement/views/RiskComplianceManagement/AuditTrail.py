"""Procurement 6.17 Risk & Compliance Management - the audit trail register and its seals.

NavERP.md bullet 3, **Audit Trail & Logging**: *"Tamper-proof logs of every action taken in the
system for audit purposes."*

Six routes: the filtered register over ``core.AuditLog``, its CSV export, the seal register, one
seal's detail page, and the two POST verbs - seal now, and verify one seal.

---

**The page never says tamper-proof, and that is the point.** ``core.AuditLog`` is an ordinary
table with no hash, no sequence number and nothing preventing an UPDATE or a DELETE, so what these
pages offer is tamper-EVIDENCE: a change is DETECTABLE afterwards and the verifier names the entry
it happened to. ``AuditSeal.TAMPER_NOTE`` says exactly that, it is pinned into the context as
``tamper_note``, and it is rendered on all three pages. A security control people wrongly believe
in is worse than no control at all.

**The register reuses the trail that already exists.** ``procurement_activity_qs(tenant)`` from
``views/_helpers.py`` is the app's single definition of "which audit rows are procurement's" - it
is what the 6.1 activity feed renders, and a second queryset here would be two answers to one
question that drift apart. This module adds the compliance-register half on top of it: the whole
workspace rather than "my actions", no default time window, an export, and the seal chain.

**What the register shows and what a seal covers are deliberately different scopes.** The register
is filtered to procurement content types, because it is procurement's page. A seal covers the
tenant's WHOLE audit range by id, because a chain over a filtered subset is not a chain: a deleted
row would be indistinguishable from a row the filter never included.

---

**Guards, in the order a reviewer looks for them:**

* **Every view refuses a tenant-less user outright** rather than filtering by ``tenant=None``.
  That is not the usual "renders empty" case (multi-tenancy rule 1): ``AuditLog.tenant`` is
  NULLABLE, so ``filter(tenant=None)`` matches every unattributed row in the install and would be
  a real cross-workspace read on the one page where that matters most.
* ``auditseal_create`` is ``@tenant_admin_required`` + ``@require_POST``; ``auditseal_verify`` is
  ``@login_required`` + ``@require_POST``. Verification is deliberately NOT admin-gated: it is
  read-mostly, and a control only an administrator can check is a control nobody checks.
* **Every cell of the CSV goes through ``csv_safe``** (imported from ``views/_helpers.py``, not
  re-written here). ``target``, the user label and the ``changes`` JSON are all user-authored, and
  a spreadsheet EXECUTES a cell that opens with ``=``, ``+``, ``-`` or ``@``.
* **Junk GET values narrow nothing rather than 500ing** (L11/L44): ints go through
  ``as_db_int`` - which refuses ``abc``, the superscript ``2`` and an over-range 20-digit value -
  and ``action`` is resolved against ``AuditLog.ACTION_CHOICES``. A date that is not ISO
  (``9999-99-99``, ``lastweek``) is ignored, and the filter bar says so rather than silently
  disagreeing with itself.
* **Query shape.** The register renders a user and a content type per row, so
  ``procurement_activity_qs`` select_relates both - without it a page of 30 rows is 60 extra
  queries. ``chain_status`` is ONE query over seals and never reads the log. Both seal registers
  ``.defer("row_fingerprints")`` so the locator list is not dragged into a list page.

**Context contracts pinned by ``.claude/tasks/contract-procurement-6.17.md`` 1:**

``audit_trail``      -> crud_list's ``object_list`` / ``page_obj`` / ``q``, plus ``action_choices``,
                        ``content_types``, ``users``, ``retention_note``, ``chain_status``,
                        ``tamper_note``, ``export_query``.
``auditseal_list``   -> crud_list's ``object_list`` / ``page_obj`` / ``q``, plus ``stats``,
                        ``chain_status``, ``is_admin``.
``auditseal_detail`` -> ``obj``, plus ``entries_covered``, ``verification``, ``is_admin``.

Three of those keys are LISTS OF DICTS and so carry a second contract (L41 1): ``chain_status``
is pinned in ``AuditSeal.chain_links``, ``entries_covered`` in :func:`_entries_covered` and
``verification`` in :func:`_verification_checks`. Each names its keys exactly; the templates render
those and nothing else.
"""
import csv
import json
from bisect import bisect_right
from datetime import date, datetime, time

from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.db.models import Count, Q
from django.http import HttpResponse

from apps.core.crud import apply_search, as_db_int
from apps.core.models import AuditLog
from apps.procurement.forms.RiskComplianceManagement.AuditSeals import AuditSealForm
# NOT-YET-WIRED entity of this SAME sub-module: import the entity MODULE directly, never
# ``from apps.procurement.models import X`` - the sub-package is not re-exported until the
# Integrator lands it, and a package-level import would be a star-import cycle at URLconf import
# time.
from apps.procurement.models.RiskComplianceManagement.AuditSeals import AuditSeal
from apps.procurement.views._common import *  # noqa: F401,F403
# csv_safe is SHARED (Backend rule 5) and already lives in _helpers.py, where 6.1's, 6.14's and
# 6.15's exports import it from. A second copy here would be a second place to forget a dangerous
# leading character. procurement_activity_qs is the app's one definition of the procurement trail.
from apps.procurement.views._helpers import csv_safe, procurement_activity_qs

TEMPLATE_TRAIL = "procurement/riskcompliance/audit_trail.html"
TEMPLATE_SEAL_LIST = "procurement/riskcompliance/auditseal/list.html"
TEMPLATE_SEAL_DETAIL = "procurement/riskcompliance/auditseal/detail.html"

#: Trail pages are scanned for sequence rather than paged one by one - 30/page, like 6.1's feed.
TRAIL_PER_PAGE = 30

#: Seals are few and each row carries a lot of meaning, so a shorter page reads better.
SEAL_PER_PAGE = 15

#: Ceiling on an export. Applied as a queryset slice, so it costs the same whatever the log holds;
#: the CSV states plainly when it has been truncated rather than quietly ending early.
EXPORT_ROW_LIMIT = 5000

#: How many covered entries the seal detail page previews. A seal can cover 50,000; the page is a
#: sample with its own honest label, and the Verify button is what checks all of them.
ENTRIES_PREVIEW = 50

#: Ceiling on the seal ranges loaded to label each exported row with its seal.
SEAL_MAP_LIMIT = 500

#: Badge class per verification-row state (L33 - only real theme.css classes).
CHECK_STATE_CSS = {
    "ok": "badge-green",
    "broken": "badge-red",
    "unknown": "badge-amber",
    "note": "badge-slate",
}

#: The word on that badge. The raw state token is for branching, never for reading - "note" on a
#: badge tells somebody nothing, and "Passes"/"Fails" is what they are actually looking for.
CHECK_STATE_LABEL = {
    "ok": "Passes",
    "broken": "Fails",
    "unknown": "Unknown",
    "note": "Note",
}

#: Badge class per covered-entry state.
ENTRY_STATE_CSS = {
    "intact": "badge-green",
    "modified": "badge-red",
    "missing": "badge-red",
    "inserted": "badge-amber",
}

ENTRY_STATE_LABEL = {
    "intact": "Matches seal",
    "modified": "Modified",
    "missing": "Deleted",
    "inserted": "Inserted",
}


# -- shared helpers ------------------------------------------------------------------------------

def _is_admin(request):
    """Mirrors ``@tenant_admin_required`` exactly, so a hidden button and a refused POST agree."""
    return bool(request.user.is_superuser or getattr(request.user, "is_tenant_admin", False))


def _need_tenant(request, what):
    """Refuse a tenant-less user instead of filtering on ``tenant=None``.

    Stronger than the house "renders empty" convention, and deliberately so: ``AuditLog.tenant`` is
    nullable, so ``filter(tenant=None)`` is not an empty queryset - it is every unattributed audit
    row in the installation. On an audit register that is a cross-workspace read, so the guard is a
    refusal with a sentence rather than a silently wider page.
    """
    if request.tenant is None:
        messages.error(request, f"Select a tenant workspace to {what}.")
        return redirect("dashboard:home")
    return None


def _as_date(raw):
    """An ISO date from a GET box, or ``None`` for anything else - never an exception (L44).

    ``9999-99-99``, ``lastweek`` and an empty box all land here as ``None``, which means "do not
    apply this bound". The filter bar says as much, so an ignored value is visible rather than
    silently disagreeing with the rows on screen.
    """
    raw = (raw or "").strip()
    if not raw:
        return None
    try:
        return date.fromisoformat(raw)
    except ValueError:
        return None


def _filtered_trail(request):
    """The register's queryset: the procurement trail, narrowed by every GET filter.

    **One implementation, used by both the page and the export**, so a CSV can never disagree with
    the rows the person was looking at when they pressed Export. That is also why
    :func:`audit_trail` hands ``crud_list`` empty ``search_fields`` / ``filters``: applying them
    here and there would run each filter twice, and the day one of the two lists changed the export
    would quietly stop matching.

    The int guards come from ``apps.core.crud.as_db_int`` rather than being re-written (L11): it
    refuses a non-decimal value, a Unicode superscript and an over-range 20-digit one, all three of
    which otherwise reach the database driver as a 500 on a URL anybody can type. ``action`` is
    resolved against the model's own closed vocabulary, so a junk token narrows nothing instead of
    emptying the register while the ``<select>`` still reads "Any action".
    """
    qs = apply_search(procurement_activity_qs(request.tenant),
                      request.GET.get("q", "").strip(), ("target",))

    action = request.GET.get("action", "").strip()
    if action in {value for value, _label in AuditLog.ACTION_CHOICES}:
        qs = qs.filter(action=action)

    for param, lookup in (("content_type", "content_type_id"),
                          ("user", "user_id"),
                          ("object_id", "object_id")):
        raw = request.GET.get(param, "").strip()
        if not raw:
            continue
        number = as_db_int(raw)
        # 0 is decimal and in range but can never be a pk (an AutoField starts at 1), so it is not
        # a narrowing request either - it would silently empty the register.
        if number:
            qs = qs.filter(**{lookup: number})

    date_from = _as_date(request.GET.get("date_from"))
    date_to = _as_date(request.GET.get("date_to"))
    if date_from and date_to and date_to < date_from:
        # Swapped bounds are corrected rather than fatal - show the span plainly meant.
        date_from, date_to = date_to, date_from
    if date_from:
        qs = qs.filter(at__gte=timezone.make_aware(datetime.combine(date_from, time.min)))
    if date_to:
        # An explicit aware upper bound rather than an ``at__date`` lookup: ``__date`` compiles to
        # CONVERT_TZ and returns NULL when the MySQL timezone tables are not loaded, which on this
        # project's XAMPP MariaDB they are not.
        qs = qs.filter(at__lte=timezone.make_aware(datetime.combine(date_to, time.max)))
    return qs


def _filter_options(request):
    """``(content_types, users)`` for the two FK dropdowns - options that actually appear.

    Both are subqueries over the SAME base queryset the register renders, so neither offers a
    choice that can only ever return an empty page (L39). Deliberately built from the UNWINDOWED
    trail: narrowing the dates should not make the type you were about to pick disappear.
    """
    base = procurement_activity_qs(request.tenant).order_by()
    content_types = (ContentType.objects
                     .filter(pk__in=base.values("content_type_id"))
                     .order_by("app_label", "model"))
    users = (get_user_model().objects
             .filter(pk__in=base.values("user_id"))
             .order_by("username"))
    return content_types, users


def _export_query(request):
    """The current filters as a querystring, minus ``page`` - what the Export link carries."""
    params = request.GET.copy()
    params.pop("page", None)
    return params.urlencode()


# -- the register --------------------------------------------------------------------------------

@login_required
def audit_trail(request):
    """The compliance register over ``core.AuditLog``: who did what to which record, when.

    Context (contract 1): ``object_list`` / ``page_obj`` / ``q`` from ``crud_list``, plus
    ``action_choices``, ``content_types``, ``users``, ``retention_note``, ``chain_status``,
    ``tamper_note`` and ``export_query``.

    ``crud_list`` is handed empty ``search_fields`` and ``filters`` on purpose - see
    :func:`_filtered_trail`, which has already applied both so the export cannot drift from the
    page. It still supplies the pagination and echoes ``q``.
    """
    guard = _need_tenant(request, "read the audit trail")
    if guard is not None:
        return guard

    content_types, users = _filter_options(request)
    return crud_list(
        request, _filtered_trail(request), TEMPLATE_TRAIL,
        extra_context={
            "action_choices": AuditLog.ACTION_CHOICES,
            "content_types": content_types,
            "users": users,
            "retention_note": AuditSeal.RETENTION_NOTE,
            "chain_status": AuditSeal.chain_links(request.tenant),
            "tamper_note": AuditSeal.TAMPER_NOTE,
            "export_query": _export_query(request),
        },
        per_page=TRAIL_PER_PAGE,
    )


def _seal_number_map(tenant):
    """``(starts, ranges)`` for labelling an exported row with the seal that covers it.

    Seal ranges are disjoint and ascending by construction, so one ``bisect`` per row answers
    "which seal covers entry #N" without a query per row. Bounded at ``SEAL_MAP_LIMIT``, taking the
    NEWEST seals: an export is overwhelmingly of recent activity, and the oldest seals are the ones
    least likely to be needed.
    """
    ranges = list(AuditSeal.objects.filter(tenant=tenant)
                  .order_by("-from_log_id")
                  .values_list("from_log_id", "to_log_id", "number")[:SEAL_MAP_LIMIT])
    ranges.reverse()
    return [item[0] for item in ranges], ranges


@login_required
def audit_trail_export(request):
    """The register's rows as CSV - the same filters, the same order, one extra column.

    The extra column is the seal covering each entry, which is what makes the file evidence rather
    than a listing: a reader can see which rows are inside a sealed range and which are not yet
    covered by one.

    **Every cell goes through ``csv_safe``.** ``target``, the user label and the ``changes`` JSON
    are user-authored, and Excel executes a cell opening with ``=``, ``+``, ``-`` or ``@`` -
    including one hidden behind a leading TAB. The helper is the app-wide one from
    ``views/_helpers.py``; this module does not define a second.

    Not admin-gated: it exports exactly the rows the person can already read on the page, with the
    same tenant filter, so gating the download but not the page would be theatre.
    """
    guard = _need_tenant(request, "export the audit trail")
    if guard is not None:
        return guard

    rows = list(_filtered_trail(request)[:EXPORT_ROW_LIMIT + 1])
    truncated = len(rows) > EXPORT_ROW_LIMIT
    rows = rows[:EXPORT_ROW_LIMIT]
    starts, ranges = _seal_number_map(request.tenant)

    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = (
        f'attachment; filename="audit-trail-{timezone.localdate():%Y%m%d}.csv"')
    writer = csv.writer(response)
    writer.writerow([csv_safe(column) for column in (
        "Entry", "When", "User", "Action", "Record type", "Object id", "Target", "Changes",
        "Sealed by")])

    for row in rows:
        index = bisect_right(starts, row.id) - 1
        sealed_by = ""
        if index >= 0 and ranges[index][1] >= row.id:
            sealed_by = ranges[index][2]
        writer.writerow([csv_safe(cell) for cell in (
            row.id,
            row.at.isoformat() if row.at else "",
            (row.user.get_full_name() or row.user.username) if row.user else "",
            row.get_action_display(),
            f"{row.content_type.app_label}.{row.content_type.model}" if row.content_type else "",
            row.object_id or "",
            row.target or "",
            # JSON rather than str(dict): a Python repr in an audit export is not a format anybody
            # can load back, and default=str keeps a Decimal or a date from raising mid-export.
            json.dumps(row.changes, sort_keys=True, default=str) if row.changes else "",
            sealed_by,
        )])

    # Footer rows rather than a preamble: a note above the header would break every reader that
    # expects the first line to be the header.
    writer.writerow([])
    writer.writerow([csv_safe(AuditSeal.TAMPER_NOTE)])
    if truncated:
        writer.writerow([csv_safe(
            f"Truncated at {EXPORT_ROW_LIMIT} entries. Narrow the dates or the filters to export "
            f"the rest - this file is not the whole range you asked for.")])
    return response


# -- the seal register ---------------------------------------------------------------------------

@login_required
def auditseal_list(request):
    """The seal register: every digest taken over this workspace's trail, newest first.

    Context (contract 1): ``object_list`` / ``page_obj`` / ``q`` from ``crud_list``, plus
    ``stats`` (``.seals .verified .broken``), ``chain_status`` and ``is_admin``.

    ``stats`` is ONE aggregate rather than three counts, and ``.verified`` / ``.broken`` count the
    stored stamps - a seal nobody has verified is in neither, which is why they do not add up to
    ``.seals`` and why the page labels the difference instead of hiding it.

    **No Edit and no Delete column**, by design (model docstring): a seal whose digest can be
    edited proves nothing, and deleting one breaks the chain it exists to protect. The page says so
    where a reviewer would look for the buttons.
    """
    guard = _need_tenant(request, "review the audit seals")
    if guard is not None:
        return guard

    base = AuditSeal.objects.filter(tenant=request.tenant)
    stats = base.aggregate(
        seals=Count("id"),
        verified=Count("id", filter=Q(last_verify_ok=True)),
        broken=Count("id", filter=Q(last_verify_ok=False)),
    )
    # .defer() keeps the per-entry locator list - which can hold 50,000 pairs - out of a page of
    # 15 rows that never renders it.
    qs = base.defer("row_fingerprints").select_related("prev_seal", "sealed_by")
    return crud_list(
        request, qs, TEMPLATE_SEAL_LIST,
        search_fields=["number", "note"],
        extra_context={
            "stats": stats,
            "chain_status": AuditSeal.chain_links(request.tenant),
            "is_admin": _is_admin(request),
        },
        per_page=SEAL_PER_PAGE,
    )


def _entries_covered(seal, limit=ENTRIES_PREVIEW):
    """The first ``limit`` entries of a seal's range, each marked against its fingerprint.

    Cheap: one indexed range read plus ``limit`` hashes. It is a SAMPLE and the page says so -
    the Verify button is what re-hashes the whole range.

    A sealed entry that is no longer in the range is merged back in as a ``missing`` row, so a
    DELETION is visible on the page rather than only in a count. The ceiling logic is what keeps
    that honest: when the live read filled the window, only sealed ids below the last live id can
    be called missing; when it did not, the whole range was read and any absent sealed id is gone.

    ROW-DICT CONTRACT (L41 1) - every entry carries EXACTLY::

        {"id":           int,
         "at":           datetime | None,     # None on a missing row
         "action":       str,                 # display label, "" on a missing row
         "target":       str,                 # user-authored; never rendered with |safe
         "user":         str,                 # resolved label, "" when the row has no user
         "content_type": str,                 # "app.model", "" when null
         "state":        str,                 # "intact"|"modified"|"missing"|"inserted"
         "state_css":    str,                 # a real theme.css badge class (L33)
         "state_label":  str}
    """
    live = list(AuditLog.objects
                .filter(tenant_id=seal.tenant_id,
                        id__gte=seal.from_log_id, id__lte=seal.to_log_id)
                .select_related("user", "content_type")
                .order_by("id")[:limit])
    fingerprints = seal.fingerprint_map
    live_ids = {row.id for row in live}
    ceiling = live[-1].id if len(live) == limit else seal.to_log_id

    entries = []
    for row in live:
        expected = fingerprints.get(row.id)
        if expected is None:
            state = "inserted"
        elif AuditSeal.row_fingerprint(row) == expected:
            state = "intact"
        else:
            state = "modified"
        entries.append({
            "id": row.id,
            "at": row.at,
            "action": row.get_action_display(),
            "target": row.target or "",
            "user": (row.user.get_full_name() or row.user.username) if row.user else "",
            "content_type": (f"{row.content_type.app_label}.{row.content_type.model}"
                             if row.content_type else ""),
            "state": state,
            "state_css": ENTRY_STATE_CSS[state],
            "state_label": ENTRY_STATE_LABEL[state],
        })

    for log_id in fingerprints:
        if log_id not in live_ids and log_id <= ceiling:
            entries.append({
                "id": log_id, "at": None, "action": "", "target": "", "user": "",
                "content_type": "", "state": "missing",
                "state_css": ENTRY_STATE_CSS["missing"],
                "state_label": ENTRY_STATE_LABEL["missing"],
            })

    entries.sort(key=lambda entry: entry["id"])
    return entries[:limit]


def _verification_checks(seal, entries):
    """The seal's state as a list of named checks. **Reads no more than one COUNT query.**

    Deliberately cheap, because this runs on every page view: re-hashing a 50,000-entry range to
    render a detail page would make the page unopenable on exactly the workspace that needs it
    most. Each row says what it actually checked, and the last two are honest about what they do
    NOT check - a stored stamp is the record of a check somebody ran, and the storage itself is
    not immutable at all.

    ROW-DICT CONTRACT (L41 1) - every entry carries EXACTLY::

        {"check":       str,   # the name of the check
         "state":       str,   # "ok" | "broken" | "unknown" | "note" - for branching
         "state_css":   str,   # a real theme.css badge class (L33)
         "state_label": str,   # the word that goes ON the badge
         "detail":      str}   # one sentence saying what was and was not established
    """
    live_count = AuditLog.objects.filter(
        tenant_id=seal.tenant_id,
        id__gte=seal.from_log_id, id__lte=seal.to_log_id).count()
    delta = live_count - seal.row_count
    if delta == 0:
        coverage = ("ok", f"{seal.row_count} entries are in {seal.range_label}, exactly as many as "
                          f"were sealed.")
    elif delta < 0:
        coverage = ("broken", f"{-delta} of the {seal.row_count} sealed entries are GONE: "
                              f"{live_count} remain in {seal.range_label}.")
    else:
        coverage = ("broken", f"{delta} entries have appeared inside {seal.range_label} since it "
                              f"was sealed; a sealed range should never grow.")

    disturbed = [entry for entry in entries if entry["state"] != "intact"]
    if not entries:
        sample = ("unknown", "There are no entries left in this range to check.")
    elif disturbed:
        first = disturbed[0]
        sample = ("broken", f"Entry #{first['id']} in the sample below is {first['state_label']}. "
                            f"Press Verify to re-hash the whole range.")
    else:
        sample = ("ok", f"The {len(entries)} entries shown below still match the fingerprints taken "
                        f"when the seal was made. This is a sample, not the whole range.")

    link_ok, link_detail = seal.link_state()

    if seal.last_verify_ok is None:
        stamp = ("unknown", "This seal has not been fully verified since it was taken. Press "
                            "Verify to re-hash every entry it covers.")
    elif seal.last_verify_ok:
        stamp = ("ok", f"Last full verification passed on "
                       f"{timezone.localtime(seal.last_verified_at):%d %b %Y %H:%M}: "
                       f"{seal.last_verify_detail}")
    else:
        stamp = ("broken", f"Last full verification FAILED on "
                           f"{timezone.localtime(seal.last_verified_at):%d %b %Y %H:%M}: "
                           f"{seal.last_verify_detail}")

    checks = [
        ("Coverage", coverage[0], coverage[1]),
        ("Sample of covered entries", sample[0], sample[1]),
        ("Chain link", "ok" if link_ok else "broken", link_detail),
        ("Last full verification", stamp[0], stamp[1]),
        ("Storage", "note",
         "The log table itself is not immutable and these stamps are ordinary columns. A seal "
         "makes a change detectable, never impossible - the proof is re-running the verification, "
         "not the badge above it."),
    ]
    return [{"check": name, "state": state, "state_css": CHECK_STATE_CSS[state],
             "state_label": CHECK_STATE_LABEL[state], "detail": detail}
            for name, state, detail in checks]


@login_required
def auditseal_detail(request, pk):
    """One seal: what it covers, what state it is in, and a sample of the entries inside it.

    Context (contract 1): ``obj``, plus ``entries_covered``, ``verification`` and ``is_admin``.
    ``TAMPER_NOTE`` and ``RETENTION_NOTE`` reach the page as ``obj.TAMPER_NOTE`` /
    ``obj.RETENTION_NOTE`` - they are class attributes on the model precisely so a page cannot
    render this record without the sentence that says what it does and does not prove.
    """
    guard = _need_tenant(request, "review an audit seal")
    if guard is not None:
        return guard

    obj = get_object_or_404(
        AuditSeal.objects.select_related("prev_seal", "sealed_by"),
        pk=pk, tenant=request.tenant)
    entries = _entries_covered(obj)
    return render(request, TEMPLATE_SEAL_DETAIL, {
        "obj": obj,
        "entries_covered": entries,
        "verification": _verification_checks(obj, entries),
        "is_admin": _is_admin(request),
    })


# -- the two verbs -------------------------------------------------------------------------------

@tenant_admin_required
@require_POST
def auditseal_create(request):
    """Seal every audit entry written since the last seal. Admin-gated, POST only.

    No form page: the note is one input beside the button, and everything else about a seal is
    derived (see ``AuditSealForm``). An empty range is refused by ``seal_now`` and reported as
    information rather than an error - pressing Seal twice is a no-op, not a mistake.

    **The success path writes an audit entry recording the digest**, which is not bookkeeping: it
    puts the digest INSIDE the append-only trail, so the next seal covers it. Somebody rewriting a
    sealed entry would then also have to rewrite the audit row that records the digest of the seal
    covering it - and that row is itself sealed by the seal after that.
    """
    guard = _need_tenant(request, "seal the audit trail")
    if guard is not None:
        return guard

    form = AuditSealForm(request.POST, tenant=request.tenant)
    if not form.is_valid():
        messages.error(request, "; ".join(
            error for errors in form.errors.values() for error in errors))
        return redirect("procurement:auditseal_list")

    seal, message = AuditSeal.seal_now(request.tenant, request.user, form.cleaned_data["note"])
    if seal is None:
        messages.info(request, message)
        return redirect("procurement:auditseal_list")

    write_audit_log(request.user, seal, "create", changes={
        "range": seal.range_label,
        "row_count": seal.row_count,
        "digest": seal.digest,
        "chain_digest": seal.chain_digest,
    }, tenant=request.tenant)
    messages.success(request, message)
    return redirect("procurement:auditseal_detail", pk=seal.pk)


@login_required
@require_POST
def auditseal_verify(request, pk):
    """Re-hash one seal's whole range and stamp the result. POST only, NOT admin-gated.

    Verification is the one thing everybody should be able to do: it is read-mostly (the only write
    is the three stamps), and a tamper check that only an administrator can run is a check nobody
    runs. The result is a message naming the first offending entry when it fails.

    **A FAILURE writes an audit entry; a pass does not.** A detected tamper is exactly the event
    that must survive in the append-only trail, where the next seal will cover it. A pass is
    already recorded in the seal's own stamps, and writing one row per button press would inflate
    the very table being sealed.
    """
    guard = _need_tenant(request, "verify an audit seal")
    if guard is not None:
        return guard

    seal = get_object_or_404(AuditSeal, pk=pk, tenant=request.tenant)
    ok, detail = seal.verify()
    if ok:
        messages.success(request, detail)
    else:
        messages.error(request, detail)
        write_audit_log(request.user, seal, "update",
                        changes={"verification_failed": detail}, tenant=request.tenant)
    return redirect("procurement:auditseal_detail", pk=seal.pk)
