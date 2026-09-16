"""Projects 7.10 — ProjectFolder [PFD-]: the per-project document folder tree.

Realizes bullet **1's hierarchical storage**. One row per folder inside ONE project; ``parent`` is a
self-FK, so a folder can nest to any depth, and the materialized ``1.2.3`` code plus the per-folder
document count are **computed in the tree view** — never stored (the 7.2 WBS ``_decorate_wbs``
idiom, where a stored path is a fact that goes stale the moment a parent is renamed).

**Why a table at all.** 7.9's own sidebar comment settles it — *"the file store, **the folders** and
the VERSION HISTORY are 7.10 Document & Knowledge Management's"* — and the NavERP.md bullet says
"Hierarchical storage". M-Files-style *metadata-driven virtual* folders (a taxonomy view with no row
behind it) stay **Module 13.4's**; this is the real, project-scoped tree.

**What it is NOT.** Not a permission boundary: a folder grants nobody anything. Access to a document
is 7.9's ``DocumentShare`` (access level + claim) and permission matrices/DRM are 13.7's. A folder is
organisation, not authorisation, and no code may branch on folder membership to authorize a thing.

**Archive, don't delete.** ``is_archived`` + both stamps are VERB-WRITTEN by ``pfd_archive`` alone
(a Toggle: archiving stamps all three, unarchiving clears all three). An archived folder keeps its
documents readable through the lens while leaving the live tree; deleting a folder that still holds
documents (or child folders) is refused outright — the Deltek PIM "you cannot delete a container that
has issued documents" rule, restated for projects. ``ProjectDocument.folder`` is PROTECT, which is
the schema-level half of that guarantee.
"""
from apps.projects.models._base import *  # noqa: F401,F403
from apps.projects.models._base import models, settings


class ProjectFolder(TenantNumbered):
    NUMBER_PREFIX = "PFD"

    #: CASCADE — a folder has no life outside its project. Required: an unscoped folder tree is
    #: meaningless (a tenant-wide taxonomy is 13.4's).
    project = models.ForeignKey(
        "projects.Project", on_delete=models.CASCADE, related_name="doc_folders")
    #: NULL = a root folder. CASCADE so deleting a folder takes its subtree (documents are
    #: PROTECTed separately on `ProjectDocument.folder`, so a non-empty subtree cannot be deleted).
    parent = models.ForeignKey(
        "self", on_delete=models.CASCADE, null=True, blank=True, related_name="children")
    name = models.CharField(max_length=120)
    description = models.TextField(blank=True)
    #: Stable manual ordering within one parent; ties fall back to `name` then the unique id so
    #: paging a tree is deterministic.
    sequence = models.PositiveSmallIntegerField(default=0)

    #: VERB-WRITTEN by `pfd_archive` ONLY — a Toggle, so a restore goes through the SAME verb + audit.
    is_archived = models.BooleanField(default=False)
    archived_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        editable=False, related_name="+")
    archived_at = models.DateTimeField(null=True, blank=True, editable=False)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        editable=False, related_name="+")

    class Meta:
        ordering = ["sequence", "name", "-id"]
        unique_together = (
            ("tenant", "number"),
            # One parent cannot hold two folders of the same name. MySQL treats NULLs in a unique
            # index as distinct, so two root folders of the same name are ALSO refused in `clean()`.
            ("tenant", "project", "parent", "name"),
        )
        indexes = [
            models.Index(fields=["tenant", "project"], name="pfd_tnt_project_idx"),
            models.Index(fields=["tenant", "parent"], name="pfd_tnt_parent_idx"),
            models.Index(fields=["tenant", "is_archived"], name="pfd_tnt_archived_idx"),
        ]

    def __str__(self):
        # Guarded on `number`: an UNSAVED instance (a ModelForm re-rendering its own errors) has
        # not been through TenantNumbered.save(), and a validation page must never read " — Docs".
        return f"{self.number or 'PFD'} — {self.name}"

    # -- derived presentation helpers (never columns) -------------------------------------------

    @property
    def is_root(self):
        return self.parent_id is None

    @property
    def status_css(self):
        return "badge-muted" if self.is_archived else "badge-info"

    def ancestor_chain(self):
        """The ancestors, root-first, walking ``parent``.

        Used by ``clean()`` (cycle detection) and by the detail page's breadcrumb. A small tree walk
        is fine here: it is bounded by the tree's depth, and the LIST page never calls it (the tree
        view decorates paths in memory from the prefetched rows instead).
        """
        chain, seen, node = [], {self.pk}, self.parent
        while node is not None and node.pk not in seen:
            chain.append(node)
            seen.add(node.pk)
            node = node.parent
        chain.reverse()
        return chain

    @property
    def full_path(self):
        """"A / B / C" for the detail page and the breadcrumb."""
        return " / ".join([folder.name for folder in self.ancestor_chain()] + [self.name])

    # -- validation ------------------------------------------------------------------------------

    def clean(self):
        super().clean()
        errors = {}

        name = (self.name or "").strip()
        if not name:
            errors["name"] = "A folder needs a name."
        self.name = name

        tenant_id = getattr(self, "tenant_id", None)

        # `_id` is tested FIRST so an unset FK cannot raise RelatedObjectDoesNotExist. The narrowed
        # <select> on the form is UX; a crafted POST never goes near it, and a foreign parent would
        # graft another workspace's branch into this project's tree.
        if getattr(self, "parent_id", None):
            parent = self.parent
            if parent.pk == self.pk:
                errors["parent"] = "A folder cannot be its own parent."
            elif tenant_id and parent.tenant_id != tenant_id:
                errors["parent"] = "That folder belongs to another workspace."
            elif getattr(self, "project_id", None) and parent.project_id != self.project_id:
                errors["parent"] = "The parent folder belongs to another project."
            elif self.pk and self._is_descendant_of(parent):
                errors["parent"] = "That would move the folder inside its own subtree."
        elif getattr(self, "project_id", None) and self.pk:
            # Two ROOT folders with the same name are refused here because a MySQL unique index
            # treats NULL parents as distinct (the `unique_together` above cannot catch them).
            clash = type(self).objects.filter(
                tenant_id=self.tenant_id, project_id=self.project_id, parent__isnull=True,
                name__iexact=name).exclude(pk=self.pk)
            if clash.exists():
                errors["name"] = "This project already has a root folder with that name."

        if errors:
            raise ValidationError(errors)

    def _is_descendant_of(self, candidate):
        """True when ``candidate`` is this folder or one of its descendants (a cycle in the making).

        ``seen`` starts EMPTY and the equality test runs FIRST: seeding it with ``self.pk`` made the
        membership guard fire before the equality test, so the walk exited exactly when it reached
        ``self`` and the method could never return ``True`` — a folder cycle was creatable through
        the ordinary edit form and ``_decorate``'s ``walk(None, …)`` then dropped the branch.
        """
        seen, node = set(), candidate
        while node is not None and node.pk not in seen:
            if node.pk == self.pk:
                return True
            seen.add(node.pk)
            node = node.parent
        return False