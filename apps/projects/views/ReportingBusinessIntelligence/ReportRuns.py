"""Projects 7.16 Reporting & Business Intelligence — ProjectReportRun (the frozen answer) views.

Seven routes over one register: the list, the pack itself, the three late writes a draft still
allows (narrative / issue / archive), an admin-only delete, and a CSV of exactly what is stored.

There is **no create and no edit here** (A2.2, B1.3) and that omission is the module's design, not
a gap in it: a run is minted only by ``rep_freeze``, which pins the compute and the payload inside
one transaction, so a form able to rewrite ``data`` in place would destroy the one property that
justifies keeping the table at all — "this project has been amber for six weeks" is derivable from
nothing else. The two human-authored late writes are the commentary and the document an issued pack
is filed against, and both are gated on ``is_draft`` by their own form.

Three rules every shape below exists to keep:

* **visibility** (R7) — every fetch, the CSV included, starts from ``analytics.visible_runs``.
  A run carries no ``is_shared`` of its own; it inherits its parent question's privacy, so a
  colleague's private run does not exist for this caller. It is a **404, never a 403**.
* **no recompute** — ``run_detail`` and ``run_csv`` read the stored payload through the model's own
  thin readers (A1.5). Nothing on those two paths calls ``analytics.compute_report``: a page that
  quietly re-asked the question would stop being a record and become a second live answer that can
  disagree with the first, which is the thing a frozen run exists to prevent.
* **``obj.save()``, never ``.update()``** — ``updated_at`` is ``auto_now``, and D5 gave this table
  that column precisely so "when did this pack last change" has an honest answer. The pinned write
  split (B2.3) reserves ``.update()`` for the two ``ProjectReport`` verbs in the sibling module,
  where the opposite lie is the one being avoided.
"""
from django.urls import reverse

from apps.core.crud import crud_list
from apps.projects import analytics
from apps.projects.forms.ReportingBusinessIntelligence.ReportRuns import (
    ProjectReportIssueForm,
    ProjectReportNarrativeForm,
)
from apps.projects.models import ProjectReportRun
from apps.projects.models.ReportingBusinessIntelligence._choices import CANVAS_CHARTS
from apps.projects.views._common import (
    get_object_or_404, login_required, messages, redirect, render, require_POST,
    tenant_admin_required, timezone, write_audit_log,
)
from apps.projects.views._helpers import chart_config, chart_rows
from apps.projects.views._helpers import csv_response
from apps.projects.views._helpers import owners as owner_choices
from apps.projects.views._helpers import redirect_back_or

TEMPLATE_LIST = "projects/reporting/reportrun/list.html"
TEMPLATE_DETAIL = "projects/reporting/reportrun/detail.html"
# There is no TEMPLATE_FORM (B4): a run is minted by ``rep_freeze`` only, so its detail page carries
# the narrative textarea and the issue form, which is the "edit" affordance the model allows.

#: ``crud_list``'s ``(get_param, orm_lookup, is_int)`` triples — the three register filters of B2.3.
#: No lookup crosses a relation: ``_enum_values`` bails on a ``__`` and the junk value would then
#: silently empty the register instead of being ignored (L11).
RUN_FILTERS = (
    ("status", "status", False),
    ("report", "report_id", True),
    ("generated_by", "generated_by_id", True),
)

#: ``(get_param, echo_key)`` for the same three filters (R2). Two of the three rename on purpose:
#: ``report`` echoes as ``report_filter`` and ``generated_by`` as ``owner_filter``, because the
#: dropdown a reader sees is labelled "Owner" while the column it selects is the generator.
RUN_FILTER_ECHOES = (
    ("status", "status_filter"),
    ("report", "report_filter"),
    ("generated_by", "owner_filter"),
)

#: Free text the register searches. ``narrative`` is the second hit field deliberately — the sentence
#: somebody typed into a pack is what a reader hunts for — and both are columns on this row, so the
#: search drags in no JOIN (``rep_list``'s rule for the same reason).
RUN_SEARCH_FIELDS = ["title", "narrative"]


# ---------------------------------------------------------------------------------
# shared builders
# ---------------------------------------------------------------------------------
def _echoes(request):
    """The register's three filter echoes, as the stripped strings they arrived as (R2).

    Never the parsed int: ``?report=abc`` comes back as ``abc``, matches no option, and the dropdown
    renders unselected instead of claiming to have narrowed the table.
    """
    return {key: request.GET.get(param, "").strip() for param, key in RUN_FILTER_ECHOES}


# ---------------------------------------------------------------------------------
# register and pack
# ---------------------------------------------------------------------------------
@login_required
def run_list(request):
    """Every pack this caller may see, narrowed by search and the three register filters.

    A fresh workspace legitimately shows nothing on this page: the seeder ships zero runs by design
    (D25), so the template's empty state — "No reports have been frozen yet" — is the first thing
    anybody reads here.
    """
    qs = analytics.visible_runs(request).select_related("report", "generated_by", "issued_by")
    return crud_list(
        request, qs, TEMPLATE_LIST,
        search_fields=RUN_SEARCH_FIELDS,
        filters=RUN_FILTERS,
        extra_context={
            "status_choices": ProjectReportRun.STATUS_CHOICES,
            # The two dropdowns that are not model choice lists. Both come from the same visible
            # populations every page in this sub-module reads from, so a filter can never offer a
            # question or a person whose rows this caller cannot open anyway (R7).
            "reports": analytics.visible_reports(request).order_by("name"),
            "owners": owner_choices(request.tenant),
            **_echoes(request),
        },
    )


@login_required
def run_detail(request, pk):
    """The pack itself: the stored answer, the commentary, and the verbs a draft still allows.

    Hand-written because it renders a payload rather than a row (R9) — and it **recomputes
    nothing** (B2.3). ``test_reporting_views.py`` patches ``analytics.compute_report`` to raise and
    this page must still answer 200. Every figure comes off ``obj.data`` / ``obj.summary`` through
    the model's thin readers, which is also what keeps this template from indexing a JSONField: a
    missing key inside a template is a blank region at HTTP 200 (L8), whereas a missing key here is
    an empty list the partial renders as an empty table.
    """
    obj = get_object_or_404(
        analytics.visible_runs(request).select_related(
            "report", "generated_by", "issued_by", "document"),
        pk=pk)
    # The select_related above makes this an attribute read, not a query.
    report = obj.report
    chart_type = obj.chart_type
    chart_labels = obj.chart_labels
    chart_data = obj.chart_data

    return render(request, TEMPLATE_DETAIL, {
        "obj": obj,
        "report": report,
        "summary": obj.summary,
        "summary_cards": obj.summary_cards,
        "columns": obj.columns,
        "rows": obj.rows,
        "chart_type": chart_type,
        "chart_labels": chart_labels,
        "chart_data": chart_data,
        # D52's one builder, plus the single wrinkle B2.3 pins for this page: a run's canvas is
        # ``wchart{{ obj.pk }}``, so the entry is keyed to the run rather than to SINGLE_CHART_ID.
        # The canvas-vs-markup decision still comes from the helper — a page that rebuilt the entry
        # to change one id would also own a copy of the CANVAS_CHARTS rule (R6, L8).
        "chart_config": chart_config(chart_type, chart_labels, chart_data, chart_id=obj.pk),
        "chart_rows": chart_rows(chart_labels, chart_data),
        "canvas_charts": CANVAS_CHARTS,
        "caveats": obj.caveats,
        "truncated": obj.truncated,
        "rating": obj.rating,
        # The badge class is the model's own property (A1.5). Deliberately no map in this module:
        # ``analytics.RAG_CSS`` is the public copy and a third spelling here is exactly what D53
        # rejects — a badge class that stops matching the letter the compute chose.
        "rag_css": obj.rag_css,
        "narrative": obj.narrative,
        # All four status flags, because the sidebar gates three different buttons on three
        # different ones and an ``{% if obj.status == "draft" %}`` in the template would be a
        # literal compared against a choice key the contract already exposes (B4.4).
        "is_draft": obj.is_draft,
        "is_issued": obj.is_issued,
        "is_archived": obj.is_archived,
        "is_editable": obj.is_editable,
        # Earlier freezes of this same question, newest first (Meta.ordering), minus this one.
        # Through ``visible_runs`` rather than the pinned raw ``tenant=`` filter: R7 makes the
        # helper the ONE fetch shape in this module, and the two agree for every report whose run
        # this caller was allowed to open — visibility is inherited from the parent, not per row.
        "runs": analytics.visible_runs(request).filter(report=report).exclude(pk=obj.pk)[:5],
        # The copy-panel URL only; every in-page button uses ``{% url %}`` (``rep_detail``'s rule
        # for the same key). It is reversed here because the route exists, so a typo is a crash.
        "csv_url": reverse("projects:run_csv", args=[obj.pk]),
        "document": obj.document,
    })


# ---------------------------------------------------------------------------------
# verbs (POST only)
# ---------------------------------------------------------------------------------
@login_required
@require_POST
def run_narrative(request, pk):
    """Rewrite the commentary. Nothing else on the row is reachable through this route.

    The draft gate lives in the form, not here: ``ProjectReportNarrativeForm.clean()`` refuses a
    non-draft instance with the sentence a reader of this page actually needs — "freeze a new run" —
    so there is no separate 403 branch to write (A2.2). There is no re-render path either: a
    POST-only verb has no form page to hand back, and the editor is an inline ``<textarea>`` on
    ``run_detail``, so the failure leaves as a message and the redirect returns to the same box.
    """
    obj = get_object_or_404(analytics.visible_runs(request), pk=pk)
    form = ProjectReportNarrativeForm(request.POST, instance=obj, tenant=request.tenant)
    if form.is_valid():
        # form.save() → instance.save(): auto_now stamps updated_at, which is the point of D5.
        # This write is the reason ``narrative`` is not simply a column the freeze already filled.
        form.save()
        write_audit_log(request.user, obj, "update", changes={"verb": "narrative"})
        messages.success(request, "Commentary saved.")
    else:
        # B2.3, verbatim. The key is guaranteed because the form's own ``clean()`` and its one field
        # are the only failure homes that can reach ``form.errors`` — the table has no ``unique_together``
        # and no ``CheckConstraint``, so nothing else adds an entry, and ``__all__`` in particular stays
        # empty (it would be a KeyError on this lookup).
        messages.error(request, " · ".join(form.errors["narrative"]))
    # One redirect for both branches, pinned by B2.3 ("and the same redirect"). ``next`` is posted
    # by the page this form sits on, so R10's helper returns the user exactly where they were and
    # falls back to this same route when it is absent.
    return redirect_back_or(request, "projects:run_detail", pk=obj.pk)


@login_required
@require_POST
def run_issue(request, pk):
    """Publish the pack: draft → issued, with the document it is filed against.

    Issuing writes three columns the form has no field for, which is why it is ``save(commit=False)``
    and three assignments — the status is the verb's own claim, never a value a client may post.
    No file upload rides this route: linking an existing document is 7.16's job, minting files is
    7.10's (A2.2), and the form's ``_reject_foreign`` is what stops a crafted POST naming another
    workspace's document.
    """
    obj = get_object_or_404(analytics.visible_runs(request), pk=pk)
    form = ProjectReportIssueForm(request.POST, instance=obj, tenant=request.tenant)
    if not form.is_valid():
        # Same shape as ``run_narrative`` — this form's own clean() and _reject_foreign both key
        # their message on ``document``, the form's single field. The model's cross-tenant document
        # rule keys there too, so a stale bad link on a stored row is a field error, not a crash.
        messages.error(request, " · ".join(form.errors["document"]))
        return redirect_back_or(request, "projects:run_detail", pk=obj.pk)
    run = form.save(commit=False)
    run.status = "issued"
    run.issued_by = request.user
    run.issued_at = timezone.now()
    # .save(), and not a queryset .update(), for the reason stated in the module docstring: an
    # audit row that claims this pack changed must not be contradicted by a stale updated_at.
    run.save()
    write_audit_log(request.user, run, "issue",
                    changes={"verb": "issue", "document": str(run.document_id or "")})
    messages.success(request, f"{run.title} issued.")
    return redirect_back_or(request, "projects:run_detail", pk=run.pk)


@login_required
@require_POST
def run_archive(request, pk):
    """Retire the pack. Terminal: an archived run is neither editable nor re-issuable.

    The already-archived branch writes nothing and logs nothing. Archive is not a toggle, so a
    double-clicked button must not produce a second audit row claiming a change that did not happen
    — the trail is the only evidence this table leaves behind, and a duplicate is a lie in it.
    """
    obj = get_object_or_404(analytics.visible_runs(request), pk=pk)
    if obj.is_archived:
        messages.info(request, f"{obj.title} is already archived.")
        return redirect("projects:run_detail", pk=obj.pk)
    obj.status = "archived"
    obj.save()
    write_audit_log(request.user, obj, "archive", changes={"verb": "archive"})
    messages.success(request, f"{obj.title} archived.")
    return redirect("projects:run_detail", pk=obj.pk)


@login_required
@require_POST
@tenant_admin_required
def run_delete(request, pk):
    """Delete a frozen pack — tenant administrators only, and only by POST.

    The decorator order is D20 (7.7's 403-vs-405 lesson): ``login_required`` outermost so an
    anonymous visitor is redirected rather than handed a 405, ``require_POST`` before the role gate
    so a member guessing at the URL gets 405 for the wrong verb instead of a 403 that leaks which
    role the route wants.

    Unlike ``rep_delete``, this one is hand-written rather than ``crud_delete``: the redirect target
    needs no pk, but the audit row needs the object while it still exists.
    """
    # select_related so the audit line below costs no extra query for the parent's number.
    obj = get_object_or_404(
        analytics.visible_runs(request).select_related("report"), pk=pk)
    # BEFORE the delete, deliberately: the audit row must outlive the object and still name the
    # report this pack answered. A run has no ``number`` of its own (A1.1), so its parent's is the
    # identifier that means something to whoever reads the trail.
    write_audit_log(request.user, obj, "delete",
                    changes={"verb": "delete", "report": obj.report.number})
    obj.delete()
    messages.success(request, "Frozen report deleted.")
    return redirect("projects:run_list")


# ---------------------------------------------------------------------------------
# export (GET, non-HTML)
# ---------------------------------------------------------------------------------
@login_required
def run_csv(request, pk):
    """The frozen rows as a download — the same cells the page shows, byte for byte.

    Straight from ``obj.columns`` / ``obj.rows``, with no recompute: a file that disagreed with the
    page it was downloaded from would undo every guarantee this table exists for (procurement's rule
    for its own snapshots, restated for a pack somebody has already circulated).

    The filename carries the parent's system-assigned number plus this row's pk, because a run has
    no number of its own (A1.1) and ``obj.title`` is text somebody typed — a newline or a quote in
    it would land in a response header the reader's browser parses.
    """
    obj = get_object_or_404(
        analytics.visible_runs(request).select_related("report"), pk=pk)
    rows = obj.rows
    write_audit_log(request.user, obj, "export", changes={"verb": "csv", "run": pk})
    return csv_response(f"{obj.report.number}-{obj.pk}.csv", obj.columns, rows)
