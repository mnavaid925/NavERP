"""Procurement 6.19 Document & Knowledge Management — KnowledgeResource.

**What it is.** The shared procurement library [PKR-]: one row per piece of reusable guidance —
the RFP template, the RFQ template, the bid-evaluation scorecard, the negotiation playbook, the
sourcing checklist, the how-to guide, the worked sample, the training deck — with the audience it
is written for, the commodity category it belongs to, an optional link to the downloadable
artifact in the 6.19 repository, and a count of how often people have reached for it. Bullet
**4 Best Practices & Templates**, and it contributes to **5 Full-Text Search & Indexing** through
the ``summary``/``body``/``tags`` columns the register sweeps.

**What it is NOT — and this is the point of the model.** A knowledge resource is CONTENT people
read, not machinery that runs. Nothing here raises a purchase, builds a questionnaire or inserts
a clause:

* the requisition templates that actually draft a purchase are **6.2**'s ``RequisitionTemplate``
  rows, which apply into a real draft requisition;
* the RFx questionnaire builder — the thing that turns "RFP template" into an event suppliers
  can answer — is **6.6**;
* the pre-approved clause library that assembles contract text is **6.8**.

This library LINKS to those and describes how to use them. It does not replace any of them, and
no view in 6.19 executes anything stored on this row. :data:`LIBRARY_NOTE` is the one sentence
that says so, printed on the register, the form and the detail page so the three surfaces cannot
describe the library differently.

**Also not Module 13.** Wikis (13.17), semantic search and auto-tagging (13.5/13.6) and
permission matrices (13.7) stay there. ``tags`` here is the same normalized CharField the
document carries, not a taxonomy table.

**The attached file is a ``ProcurementDocument``, deliberately — there is no ``FileField`` here.**
A scorecard workbook or a playbook PDF is chosen through the ``document`` FK, so it goes through
the repository's extension allow-list, its 20 MB cap, its checksum, its text read and its
approval step, and it gains a revision chain. A second upload path on this model would skip all
five and leave the library holding an unversioned copy of a file that also exists, differently,
somewhere else. One artifact, one place, one history.

**``usage_count`` is a CLICK COUNTER, never a derived metric and never an audit trail.** It
counts presses of the "use this" button and nothing else: it does not know who pressed it, it is
not evidence that a template was actually used on a sourcing event, and it can never be
reconciled against anything. Per-user usage ledgers are 6.17 / Module 13 territory. It is
incremented with an atomic ``F("usage_count") + 1`` in the view verb — see
``knowledgeresource_use`` — so two people opening the same playbook in the same second both
count. A read-modify-write would silently drop one of them.

**``is_featured`` is the guided-buying shelf, not a permission.** It decides what surfaces first
on the register — nothing more. It is not "approved for use", it does not gate anything and no
code may branch on it to authorize a thing. The ordering below puts featured rows first and then
falls back to ``-created_at`` and the unique ``-id``, which is what makes paging deterministic:
without the ``id`` tiebreak two rows created in the same second could swap places between page 1
and page 2 and silently duplicate one while dropping the other.
"""
from apps.procurement.models._base import *  # noqa: F401,F403

# The tag normalizer is SHARED with entity 1 on purpose: one tag typed on a document and on a
# guide has to be one tag, or the register's ?tag= substring facet finds half of them. Imported
# from the entity MODULE rather than ``apps.procurement.models`` — this sub-package is not wired
# into the package __init__ until the Integrator lands it, and a package-level re-export would be
# a star-import cycle at URLconf import time.
from apps.procurement.models.DocumentKnowledgeManagement.Documents import normalize_tags


# ---------------------------------------------------------------------------------------------
# Vocabulary. Defined at module level so the seeder, the views and the templates can read it, and
# ALSO re-exposed on the class below — which is how templates and tests reach it, since the
# *_CHOICES tuples are deliberately NOT hoisted into apps/procurement/models/__init__.py (the
# 6.14/6.15 rule that entities 1 and 3 of this sub-module follow too).
# ---------------------------------------------------------------------------------------------

#: What KIND of guidance this is. The first four are the ones the sub-module exists to hold — the
#: RFP/RFQ templates, the bid-evaluation scorecard and the negotiation playbook.
RESOURCE_TYPE_CHOICES = [
    ("rfp_template", "RFP Template"),
    ("rfq_template", "RFQ Template"),
    ("evaluation_scorecard", "Bid Evaluation Scorecard"),
    ("negotiation_playbook", "Negotiation Playbook"),
    ("checklist", "Checklist"),
    ("guide", "How-to Guide"),
    ("sample_document", "Sample Document"),
    ("training", "Training Material"),
]

#: WHAT it is about. A CHOICES field and not an FK, because there is no commodity taxonomy table
#: in this codebase to point at — inventing one here would be a second, competing category tree
#: the moment a real one lands. A fixed vocabulary is honest about being a facet.
CATEGORY_CHOICES = [
    ("general", "General"),
    ("it_software", "IT & Software"),
    ("facilities", "Facilities"),
    ("logistics", "Logistics & Freight"),
    ("professional_services", "Professional Services"),
    ("raw_materials", "Raw Materials"),
    ("capex", "Capital Equipment"),
    ("marketing", "Marketing"),
    ("other", "Other"),
]

#: WHO it is written for. A reading hint on the register, never an access control: every member
#: of the workspace can open every resource, and a resource written for Legal is not hidden from
#: a requester. Permission matrices are 13.7.
AUDIENCE_CHOICES = [
    ("all", "Everyone"),
    ("requester", "Requesters"),
    ("buyer", "Buyers"),
    ("approver", "Approvers"),
    ("legal", "Legal"),
]

STATUS_CHOICES = [
    ("draft", "Draft"),
    ("published", "Published"),
    ("archived", "Archived"),
]

#: theme.css ships ONLY badge-green / badge-red / badge-amber / badge-info / badge-muted /
#: badge-slate (L33) — a semantic badge-success/-warning/-danger renders completely unstyled.
STATUS_CSS = {
    "draft": "badge-muted",
    "published": "badge-green",
    "archived": "badge-slate",
}

#: How many rows the "start here" shelf shows above the register. A shelf that lists everything
#: is not a shelf; the cap is also what keeps that extra query bounded no matter how many rows
#: somebody stars.
FEATURED_CAP = 6

#: THE sentence about what this library is and is not. ONE constant, printed on the register, the
#: form and the detail page, so nobody can read a stored playbook as something that runs.
LIBRARY_NOTE = (
    "Guidance content, not an executable template. The requisition templates that actually raise "
    "a purchase live in 6.2, the RFx questionnaire builder in 6.6 and the pre-approved clause "
    "library in 6.8 - this library links to them, it does not replace them."
)


class KnowledgeResource(TenantNumbered):
    """One piece of reusable procurement guidance [PKR-] — a template, scorecard or playbook."""

    NUMBER_PREFIX = "PKR"

    # Re-exposed on the class so views, templates and tests reach the vocabulary through the
    # model rather than through a module path.
    RESOURCE_TYPE_CHOICES = RESOURCE_TYPE_CHOICES
    CATEGORY_CHOICES = CATEGORY_CHOICES
    AUDIENCE_CHOICES = AUDIENCE_CHOICES
    STATUS_CHOICES = STATUS_CHOICES
    STATUS_CSS = STATUS_CSS
    FEATURED_CAP = FEATURED_CAP
    LIBRARY_NOTE = LIBRARY_NOTE

    title = models.CharField(max_length=200)
    resource_type = models.CharField(max_length=22, choices=RESOURCE_TYPE_CHOICES,
                                     default="guide")
    category = models.CharField(max_length=22, choices=CATEGORY_CHOICES, default="general")
    # WARNING: a READING HINT, not an access control. Nothing in 6.19 hides a resource from a
    # user because of this column, and nothing may start: authorizing on a free-choice field
    # every author picks for themselves would grant or refuse access on the strength of a label
    # rather than a role. Per-audience visibility belongs to 13.7's permission matrices, and the
    # gate that exists today is the one that already works — @login_required plus the tenant
    # filter on every queryset.
    audience = models.CharField(max_length=12, choices=AUDIENCE_CHOICES, default="all")

    summary = models.CharField(max_length=500, blank=True)
    #: The guidance itself, rendered on the detail page. User-authored prose — see the WARNING on
    #: the detail template: it is escaped with |linebreaksbr and never |safe.
    body = models.TextField(blank=True)
    tags = models.CharField(max_length=255, blank=True, help_text="Comma-separated keywords")

    # Verb-driven and therefore NOT on the form: publish and archive are POST-only actions with
    # their own audit rows. A status <select> here would let a form save skip the workflow and
    # the audit trail together.
    status = models.CharField(max_length=12, choices=STATUS_CHOICES, default="draft")

    # WARNING: the guided-buying SHELF flag, and nothing more. It decides display order and it
    # decides nothing else — it is not "approved", not "mandatory" and not a permission, and no
    # code may branch on it to allow or refuse an action. A starred resource carries exactly the
    # authority of an unstarred one; what makes a rule binding is a published ProcurementPolicy
    # (advisory) or a 6.3 ApprovalRoutingRule (enforced), never a star on a library row.
    is_featured = models.BooleanField(
        default=False,
        help_text="Show this first on the library shelf. A display choice, not an approval.")

    # WARNING: a CLICK COUNTER, never a derived metric and never an audit trail. It counts
    # presses of the "use this" button; it does not know who pressed it, it does not prove a
    # template was used on any event, and it must never be read as attestation or evidence — a
    # number that cannot be reconciled against anything is not a control. The audit trail that
    # CAN answer "who did what" already exists: write_audit_log rows, which the use verb writes
    # per press. A per-user usage ledger belongs to 6.17 / Module 13, not here.
    # Written ONLY through an atomic F("usage_count") + 1 in knowledgeresource_use, so two
    # concurrent presses cannot lose a count to a read-modify-write.
    usage_count = models.PositiveIntegerField(default=0, editable=False)
    last_used_at = models.DateTimeField(null=True, blank=True, editable=False)

    review_on = models.DateField(
        null=True, blank=True,
        help_text="When somebody should read this again. Guidance goes stale quietly.")

    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
                              null=True, blank=True,
                              related_name="procurement_knowledge_owned",
                              help_text="Who is answerable for keeping this guidance current")
    # THE FK THAT KEEPS ONE FILE IN ONE PLACE: the downloadable workbook or PDF is an ordinary
    # ProcurementDocument, so it inherits the revision chain, the approval step and the text
    # search instead of this row carrying a second, unversioned copy. ``related_name`` is
    # ``knowledge_resources`` because entity 1's detail view already reads that reverse accessor.
    document = models.ForeignKey(
        "procurement.ProcurementDocument", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="knowledge_resources",
        help_text="The downloadable artifact in the repository - so it gets revisions and "
                  "approval like everything else.")

    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
                                   null=True, blank=True, editable=False, related_name="+")

    class Meta:
        # Featured first — that IS the shelf — then newest, then the unique id. The id tiebreak
        # is not decoration: ``-is_featured, -created_at`` alone leaves rows created in the same
        # second in an order the database is free to choose per query, and an unstable sort under
        # a Paginator silently repeats one row on page 2 while dropping another entirely.
        ordering = ["-is_featured", "-created_at", "-id"]
        unique_together = ("tenant", "number")
        indexes = [
            models.Index(fields=["tenant", "status"], name="prc_pkr_tnt_status_idx"),
            models.Index(fields=["tenant", "resource_type"], name="prc_pkr_tnt_type_idx"),
            # Serves the shelf query (tenant + is_featured + status) and the featured facet.
            models.Index(fields=["tenant", "is_featured"], name="prc_pkr_tnt_feat_idx"),
        ]
        verbose_name = "Knowledge Resource"
        verbose_name_plural = "Knowledge Resources"

    def __str__(self):
        # Guarded on ``number``: an UNSAVED instance (a ModelForm rendering its own errors) has
        # not been through TenantNumbered.save() yet, and a validation page must never read as
        # " · Title".
        return f"{self.number or 'PKR'} · {self.title}"

    # -- presentation helpers -------------------------------------------------------------

    @property
    def tag_list(self):
        """The normalized tags as a list, for badge rendering.

        Identical to ``ProcurementDocument.tag_list`` because the two columns are normalized by
        the same :func:`normalize_tags` — one tag on a document and on a guide is one tag.
        """
        return [tag for tag in (self.tags or "").split(", ") if tag.strip()]

    @property
    def status_css(self):
        return STATUS_CSS.get(self.status, "badge-slate")

    # -- life-cycle questions -------------------------------------------------------------

    @property
    def is_review_due(self):
        """Computed against today rather than stored, so a row cannot go stale in the database.

        The register runs the same comparison in SQL for its review stat tile, so the badge on a
        row and the count above it always agree.
        """
        return bool(self.review_on and self.review_on <= timezone.localdate())

    @property
    def has_been_used(self):
        """Whether anybody has pressed "use this" yet. Reads the counter, claims nothing more."""
        return bool(self.usage_count)

    # -- validation -----------------------------------------------------------------------

    def clean(self):
        super().clean()
        errors = {}

        # Same normalizer as the document, deliberately — see :func:`normalize_tags`.
        self.tags = normalize_tags(self.tags)

        tenant_id = getattr(self, "tenant_id", None)
        if tenant_id:
            # Cross-tenant backstop on the one tenant-scoped link this model carries. The
            # narrowed <select> on the form is UX; a crafted POST never goes near it, and this FK
            # would otherwise pull another workspace's document — and its file, and its extracted
            # text — into this register through the detail page's download link.
            # ``_id`` is tested FIRST so an unset FK cannot raise RelatedObjectDoesNotExist.
            if getattr(self, "document_id", None):
                if getattr(getattr(self, "document", None), "tenant_id", None) != tenant_id:
                    errors["document"] = "That record belongs to another workspace."

        if errors:
            raise ValidationError(errors)
