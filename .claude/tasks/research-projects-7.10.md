# Research — Sub-module 7.10: Document & Knowledge Management (Module 7 — Project Management, `projects`)

> **Read this first.** 7.10 is the module's **project record of record**: it turns a project's
> documents from loose attachments into a *controlled, versioned, findable and eventually
> archived* repository — **where the file lives** (a per-project folder hierarchy), **what it is**
> (doc type, classification, owner, tags), **which revision is current** (an approved-revision
> chain with a check-out lock while somebody edits), **what to start from** (the standard
> templates and formats), **what was learned** (the lessons-learned / playbook library), and
> **when it stops being live** (retention, review dates, archiving, legal hold).
>
> **Researched 2026-09-15** against 7 products read directly — Deltek PIM, Newforma Project Center,
> M-Files, Microsoft SharePoint (versioning), Microsoft Purview (data lifecycle + records
> management), Preservica (retention & legal hold) and Atlassian Confluence — plus the in-repo
> blueprint **procurement 6.19 Document & Knowledge Management**, which is the SAME sub-module by
> name in another module and ships 4 models whose rulings transfer verbatim.
>
> **Recommended scope: 5 new tenant-scoped models** — `ProjectFolder` [PFD-],
> `ProjectDocument` [PDM-], `ProjectDocumentRevision` [PDV-], `DocumentTemplate` [DTM-],
> `KnowledgeEntry` [KNE-] — plus 3 computed pages (`doc_repository`, `doc_retention`,
> `kne_search`). One register over the 1-4 guideline is deliberate and justified in
> **Ruling 1** (bullet 1 mandates a hierarchy, which is a table; 7.9 shipped 7 tables in one pass).
>
> **The three failure modes for this pass:**
> 1. **Building the enterprise DMS.** Module 13 (`NavERP.md:1980`) owns authoring/co-editing
>    (13.1), branching/redlining/rollback (13.2), the workflow designer and e-signature (13.3),
>    cloud storage deployment (13.4), semantic search/auto-tagging (13.5/13.6), permission
>    matrices/DRM (13.7) and retention **auto-destruction** + legal hold enforcement (13.9/13.14).
>    7.10 must be **project-scoped** and must park all of that. See **Ruling 5**.
> 2. **Minting a second `core.Document` or a GFK register.** `core.Document` is the generic
>    per-record attachment (`apps/core/models/Document.py:5`); its `version` is a flat CharField
>    with no revision chain and its `GenericForeignKey` cannot be `.filter(tenant=...)`-ed, joined
>    or faceted on a register page — procurement 6.19 documented that rejection and 7.10 inherits
>    it. See **Ruling 2**.
> 3. **Re-declaring a sibling's register.** CRM 1.9 already ships `DocumentVersion` +
>    `DocTemplates` [TPL-] for contracts, HRM ships `KnowledgeBase` [KB-] / `KnowledgeArticle`
>    [KBA-] / `KbCategories` [KBC-] / `Document` [EDOC-] / `DocumentRequest` [DOCREQ-], and
>    **procurement 6.19 ships `ProcurementDocument` [PDOC-] + its revision chain +
>    `ProcurementPolicy` [PPOL-] + `KnowledgeResource` [PKR-]**. 7.10 mirrors the *idiom*, never the
>    tables. See **Ruling 4**.

---

## Repo state checked first

**LIVE_LINKS (read at run time):** `apps/core/navigation.py` carries exactly nine Module 7 entries —
`7.1` (line 1704), `7.2` (1719), `7.3` (1734), `7.4` (1749), `7.5` (1768), `7.6` (1789), `7.7` (1810),
`7.8` (1830), `7.9` (1839). **`7.10` does not exist -> it is the next unbuilt sub-module.** Modules
1-6 are complete. Migration leaf is `0013_channelmessage_chm_tnt_created_idx_and_more` ->
**7.10 claims `0014`** (`manage.py makemigrations --check --dry-run` -> *No changes detected*, so
there is no drift to absorb).

### Boundaries ALREADY RULED in code, in this module's own comments

These are not opinions — they are already asserted in the repository, and 7.10 must honour them:

| Where | What it already says |
|---|---|
| `apps/core/navigation.py:1841-1844` (7.9's sidebar comment) | bullet 2 of 7.9 maps to the SHARE register "not a document repository: **the file store, the folders and the VERSION HISTORY are 7.10 Document & Knowledge Management's**" |
| `.claude/skills/projects/SKILL.md` (7.9 section) | "7.9 ships the SHARE, never a second file store. `DocumentShare` FKs the existing `core.Document` by string — the repository, folders, metadata and **version history are 7.10's**" |
| `apps/projects/models/CollaborationCommunication/DocumentShares.py:28` | `DocumentShare.document` -> `core.Document`, `related_name="project_shares"` — **7.9 already depends on `core.Document`; 7.10 must not break it** |
| `.claude/skills/projects/SKILL.md:299-300` (7.5) | "the knowledge repository is **7.10's** (`lessons_learned` is a FIELD on the row, not a second store)" |
| `.claude/skills/projects/SKILL.md:379` (7.6) | "minutes/ceremony/repository are **7.9/7.13/7.10's**" |
| `apps/procurement/models/DocumentKnowledgeManagement/Documents.py` (6.19) | the whole rejection argument for `core.Document` and the Module-13 parking list — the sibling precedent |

### Spine entities VERIFIED (grep/read evidence)

| Entity | Verified at | What 7.10 uses it for |
|---|---|---|
| `core.Document` | `apps/core/models/Document.py:5` | The generic attachment (tenant, GFK `related`, `file`, `name`, `classification` public/internal/confidential, flat `version` CharField, `uploaded_at`). **Linked, never re-declared** — see Ruling 2 for why the *register* cannot simply be a lens over it. |
| `projects.Project` [PRJ-] | `apps/projects/models/ProjectInitiation/Projects.py` | **The owner of every 7.10 row** (project FK, CASCADE). |
| `projects.DocumentShare` [DSH-] | `apps/projects/models/CollaborationCommunication/DocumentShares.py:28` | 7.9's access layer over `core.Document` — a read-only lens from 7.10's detail pages; **not re-declared** (no second ACL; permission matrices/DRM are 13.7's). |
| `projects.ProjectMilestone` [MST-] | `ProjectPlanningScheduling/ProjectMilestones.py` | Optional real link FK: the milestone a document evidences. |
| `projects.ProjectTask` [TSK-] | `ProjectPlanningScheduling/ProjectTasks.py` | Optional real link FK: the deliverable a document belongs to. |
| `core.AuditLog` | `apps/core/` + `apps/core/utils.write_audit_log` | Every verb's trail; verbs go in `changes`, never in `action` (varchar(10)). |
| `TenantNumbered` / `TenantOwned` | `apps/projects/models/_base.py` | The numbering bases every 7.10 register uses (`next_number`), exactly as 7.9's seven tables do. |

**Prefix availability (checked, not assumed).** `PFD`, `PDM`, `PDV`, `DTM`, `KNE` appear as NO
`NUMBER_PREFIX` anywhere in `apps/` -> free. Taken and therefore **unusable** here: `PDOC`
(procurement 6.19), `DOCREQ` (hrm 3.26), `EDOC` (hrm), `KB`/`KBA`/`KBC` (crm/hrm knowledge),
`TPL` (crm 1.9 `DocTemplates`), `LSN` (scm labor), `ARL` (inventory alert rules), `RTV` (procurement
returns), `RSP`/`RTE`/`RAL` (7.3), `DSH`/`CHN`/`CHM`/`MTG`/`AGI`/`MAIT`/`NTF` (7.9). The route-name
namespaces `pfd_`, `pdm_`, `pdv_`, `dtm_`, `kne_` are unused in `apps/projects/urls/` (checked by
enumerating the `name=` prefixes of every URL module in the app).

---

## Rulings (the decisions this build turns on)

### Ruling 1 — Scope: 5 registers, because bullet 1 mandates a hierarchy
The five NavERP.md bullets map to **five tables**, and the count is deliberate rather than drifted:
bullet 1 ("Hierarchical storage") is a *tree*, and a tree is a table — 7.9's own sidebar comment
assigns "the file store, **the folders** and the VERSION HISTORY" to 7.10, so parking the hierarchy
in 13.4 would contradict a ruling this module already made. The other four bullets are the 6.19
shape scaled to projects: a metadata register, an immutable revision chain, a templates/standards
library and a knowledge library. 7.9 shipped **7 tables in 5 entity files** in one pass, so 5 here
is inside the module's demonstrated envelope. If Phase 2 (`todo`) must cut, the cut order is
**`DocumentTemplate` -> park bullet 2's register to 7.19 (master data)** — never the revision chain
and never the knowledge library, which are the only two bullets no sibling owns.

### Ruling 2 — The register is 7.10's own row with REAL link FKs; `core.Document` is linked, not replaced
`core.Document` cannot carry this sub-module: no project FK, no doc type/status/owner, a flat
`version` CharField instead of a chain, and a `GenericForeignKey` that cannot be tenant-filtered,
joined or faceted — the exact argument procurement 6.19 recorded ("an IDOR surface the moment a
register lists it"). So `ProjectDocument` is a real tenant+project-scoped row with **four real link
FKs** (project, folder, optional milestone, optional task) declared **by string** so this package
imports no sibling app at import time. `core.Document` is **not touched**: no import, no FK, no
migration. 7.9's `DocumentShare` (which does FK `core.Document`) keeps working untouched, and 7.10
surfaces it as a read-only lens on the detail page. **Consequence to state honestly on the page:**
the generic attachment drawer and the project repository are two different shelves; a file that
lives in the GFK attachment path is not automatically in the repository.

### Ruling 3 — Version control is a linear APPROVED-revision chain with a check-out LOCK (6.19 verbatim)
The market splits "versions" in two: a **revision chain** (only the latest *approved* revision is
the accessible one) and a **check-out lock** (SharePoint/M-Files: check out to edit exclusively,
check in to publish; others see the last published version meanwhile). 7.10 ships both, and
**reuses 6.19's proven chain rules verbatim** rather than inventing a second one:
`revision_no` allocated inside `transaction.atomic()` behind `select_for_update()` on the parent;
upload never moves the pointer; approve refuses `revision_no <= current_revision_no`;
`current_revision_no` is an **integer pointer** (0 = none) resolving through the `revisions`
reverse accessor, never a circular FK; an older approved revision **keeps** `is_approved=True`
("only one is current" is expressed by the pointer, never by un-approving history); immutability is
**structural** (no edit url/view/template; every column but `change_note` is `editable=False`).
The check-out lock is a **state pair on the parent** (`is_checked_out`, `checked_out_by/at`) moved
only by POST-only verbs `pdm_checkout` / `pdm_checkin`, with the honest consequence printed on the
page: it is a **cooperative lock inside one installation**, not an OS-level file lock. Conflict
resolution therefore means *"whoever holds the check-out wins; a second upload is refused while a
lock is held"* — not a merge tool (13.2 owns merging/branching/redlining).

### Ruling 4 — The knowledge library is CONTENT, not machinery; templates ride in it as a KIND
6.19's `KnowledgeResource` already proves the idiom: RFP templates, scorecards and playbooks live in
ONE library register distinguished by `resource_type`, with an optional link to a repository
document and a click-only `usage_count`, and an explicit docstring that nothing there *executes*.
For projects the same register is `KnowledgeEntry` [KNE-] with `kind` covering
`template / standard / playbook / checklist / lesson_learned / retrospective` — which is what makes
bullet 2 (templates & standards) and bullet 4 (knowledge base & lessons learned) **two sidebar
leaves over two lenses of one table** rather than two near-duplicate tables. `DocumentTemplate`
[DTM-] is therefore recommended as a **separate small register only when the standard has a file and
a publishable version** (the Deltek "Publish a Template" shape: category/pool, `version`,
`is_active`, format-lock flag); otherwise bullet 2 collapses entirely into `KnowledgeEntry.kind`.
**Phase 2 must decide this once, explicitly** — the safe default is: `DocumentTemplate` ships for
file-backed standards, and every lesson/playbook/checklist stays in `KnowledgeEntry`.

### Ruling 5 — Retention is a documented INTENT plus verbs; enforcement is Module 13's
Preservica/Purview give the vocabulary — retention period, retain-then-delete, disposition review,
event-based retention, legal hold **overrides** retention, immutable once held, defensible audit
log. None of that machinery exists here, and 6.19 already ruled the line: "`retention_until` here is
a FLAG a human reads, never an action — nothing in this sub-module deletes anything on a schedule",
with auto-destruction and legal-hold **enforcement** at 13.9/13.14. So 7.10 ships:
`retention_months` + the computed `retain_until` / `is_retention_due`, a `review_on` review date
(the 6.19 reminder idiom), `is_archived` + `archived_by`/`archived_at` moved only by a Toggle verb,
and an `is_legal_hold` + `hold_reason` pair that **blocks** delete and archive in `clean()` and on
the delete view — a recorded hold, not an immutable vault. The **Retention & Archiving board** is a
computed page (counts, overdue retention, held rows, archived rows) whose "notify" affordance runs
one **idempotent in-app reminder** action only: there is no scheduler and no mail worker in this
repo (the 6.3/6.19 ruling), so "automated" never means cron.

### Ruling 6 — Full-text search is a denormalized copy with an honest caveat
6.19's proven shape: the text of record lives on the approved revision; the parent carries a
**denormalized search copy** refreshed by exactly two writers (the approve verb and a re-index Run),
so one `icontains` sweep over the register matches file contents without joining the revision table
on every keystroke. The sweep is joined from **4+ characters** only (a 1-3 char `?q=` skips the
TextField scan, because Paginator runs it twice), extraction is a **lazy `pdfplumber` import with a
never-raising fallback**, bounded by both a page cap and a character cap, and it is honest that a
scanned image has no text layer. Semantic search, embeddings and auto-tagging stay 13.5/13.6's.
**7.10 adds what 6.19 does not need: the same honesty for the knowledge register** — a lesson with
no body matches on title/tags only, and the empty state says exactly that.

---

## Leaders surveyed (with source links)

1. **Deltek PIM** (Project Information Management for A&E firms) — the closest product to this
   sub-module: emails, documents and drawings unified per project, with a drawing/document register
   and a "document placeholder" container per controlled document.
   [Product page](https://www.deltek.com/products/delivery-assurance/project-information-management/) ·
   [Placeholders](https://dsm.deltek.com/product/PIM/24.0/Create_Manage_Document_Placeholders.html) ·
   [Publish a Template](https://help.deltek.com/product/PIM/26.0/Publish_Template.html)
   - *Document placeholder*: "a container used to store and manage **all versions** of a project
     document… Each placeholder has an assigned **version numbering scheme**, and an originating
     organization"; one placeholder can hold multiple **renditions** (Word/TIFF/PDF); placeholders
     are created **in advance** for documents you expect to receive; uploading a document
     auto-matches it to a placeholder **by title**; editing a property in the "causing revision
     change" set **creates new revisions for all documents issued against it**; a placeholder can be
     **cloned** (same or different project); **deletion is refused** once documents have been issued
     against it (or an issue is pending); placeholders are bulk-imported from CSV/TXT; **baskets**
     group and share documents by email, per rendition.
   - *Templates*: published to one or more **template pools**, with per-template **default publish
     pools** and **entity classes required for merging** (e.g. picking the project class forces the
     user to choose a project when publishing a document created from the template); "template body
     text required" can be enforced; version comments are captured at publish.
2. **Newforma Project Center** (AEC project information management; on-prem and cloud packages) —
   the feature vocabulary of project document control: *Document Control*, *File Manager*,
   *Aggregate Search*, *Action Items*, *Contract Administration*, *Communication Management*,
   *Share Files*, and an explicit **archiving + data-migration-at-closeout** story.
   [Product page](https://www.newforma.com/products/project-center/)
3. **M-Files** (metadata-driven document management; "Project Information Management" is a named use
   case) — organizes "documents by **what they are**, not where they are stored"; metadata links
   documents to clients, projects and processes; security, permissions, **retention** and audit are
   applied automatically across the document lifecycle; version management and check-in/check-out
   are platform capabilities; "Capture and Reuse Knowledge — preserve organizational knowledge by
   connecting documents, decisions, and expertise".
   [Features](https://www.m-files.com/features/)
4. **Microsoft SharePoint / Microsoft 365 document libraries** — the check-in/check-out and version
   model everyone else is compared against: **major vs minor versions**, a per-item **version
   history** with restore (restoring adds a NEW version), per-version delete, **limit the number of
   versions/drafts retained**, **require files to be checked out** before editing, content approval,
   and draft visibility settings.
   [Versioning](https://support.microsoft.com/en-us/office/enable-and-configure-versioning-for-a-list-or-library-1555d642-23ee-446a-990a-bcab618c7a37)
5. **Microsoft Purview — Data Lifecycle Management** — retention **policies** (workload-wide,
   retain / delete / retain-then-delete) vs retention **labels** (per-item exceptions, published or
   auto-applied), plus mailbox/archive and inactive-mailbox retention. The vocabulary for 7.10's
   retention *intent* columns.
   [Data lifecycle](https://learn.microsoft.com/en-ca/purview/data-lifecycle-management)
6. **Microsoft Purview — Records Management** — label items as a **record** or **regulatory record**
   (a regulatory record cannot be removed even by a global administrator, and its period can only be
   extended), **file plan** import of an existing retention plan, **event-based retention**,
   **disposition review** + proof of deletion, export of disposed items. This is where *stored*
   enforcement lives in the market — and it is Module 13's here.
   [Records management](https://learn.microsoft.com/en-us/purview/records-management)
7. **Preservica — Automated retention and legal hold** — retention schedules and holds in one
   archive: **legal hold overrides retention automatically**, multiple holds are handled, there is a
   defensible audit log of hold actions, immutability is enforced "at the system level, not just by
   policy", authenticity is guaranteed by a cryptographic fingerprint taken at preservation time,
   metadata is bound to the record, and disposition/expiry review serves auditors and courts.
   [Automated retention & legal hold](https://preservica.com/automated-retention-and-legal-hold)
8. **Atlassian Confluence** (knowledge-base reference) — **spaces** and an intuitive content
   hierarchy, **page templates** with template categories, **labels**, "find what you need with
   advanced search, labels, and an intuitive content hierarchy", inline and page comments with
   mentions, notifications when someone is tagged or assigned a task, and a personalised home feed.
   [Features](https://www.atlassian.com/software/confluence/features)

**The strongest "leader" is in this repo: procurement 6.19 Document & Knowledge Management**
(`apps/procurement/models/DocumentKnowledgeManagement/`, NavERP.md `### 6.19`) — the SAME sub-module
name in Module 6, already built and reviewed here, with 4 models: `ProcurementDocument` [PDOC-]
(the register: real link FKs instead of a GFK, `extracted_text` search copy, `retention_until` as a
human-read flag), `ProcurementDocumentRevision` (immutable; `revision_no`; SHA-256 checksum; text of
record), `ProcurementPolicy` [PPOL-] (library + supersession chain) and `KnowledgeResource` [PKR-]
(templates/scorecards/playbooks; `usage_count` click counter; `is_featured` shelf). Its documented
rejection of `core.Document` and its parking list for Module 13 are the strongest available evidence
of what this codebase accepts, so 7.10 **mirrors its architecture and reuses its invariants** rather
than re-deriving them.

**Not reached (recorded so nobody assumes coverage):** Oracle Aconex / Oracle construction project
document management returned HTTP 403 and InEight's document-control page returned HTTP 404 in this
session. The eight sources above were read directly. Transmittals and multi-party
*issue-for-construction* are therefore described from Deltek/Newforma vocabulary only — and are
parked to 7.14 (client & external collaboration) and Module 13 in any case.

---

## Feature catalog (this sub-module only)

### Bullet 1 — Document Repository & Folders ("hierarchical storage, metadata tagging, and project-specific organization")
- **Per-project folder tree** — nested folders inside one project, so a project's files are organized
  the way the project is (drawings / specs / reports / handover). · seen in: Deltek PIM (project
  document sets), Newforma (*File Manager*), SharePoint (document library folders) · priority:
  **table-stakes** · spine: **new table `ProjectFolder`** · buildable now
- **Named document register per project** — one row per controlled document with its real links
  (project, folder, milestone, task), so the register can be filtered and faceted instead of
  scanned. · seen in: Deltek PIM (document register), Newforma (*Document Control*), 6.19
  (`ProcurementDocument`) · priority: **table-stakes** · spine: **new table `ProjectDocument`** ·
  buildable now
- **Metadata tagging** — doc type (charter/plan/report/status update/minutes/specification/drawing/
  other), classification (public/internal/confidential — the `core.Document` vocabulary), owner,
  tags. · seen in: M-Files (metadata-driven, "what they are, not where they are stored"), 6.19
  (`tags` normalized CharField, `document_type`, `classification`) · priority: **table-stakes** ·
  spine: new columns on `ProjectDocument` · buildable now
- **Faceted register** — filters by folder, doc type, status, owner, tag, classification, plus
  search, Actions and pagination (the app-wide list-page contract). · seen in: M-Files, 6.19's
  register facets · priority: **table-stakes** · spine: the list view · buildable now
- **Expected-document placeholders** — a named slot created *before* the file arrives, matched on
  upload, and refusing deletion once a document has been issued against it. · seen in: **Deltek PIM
  (document placeholder)** · priority: **differentiator** · spine: `ProjectDocument` with
  `status="expected"` (a state, never a second table — Ruling 1's cap) · buildable now
- **Repository overview** — computed counts (documents, folders, drafts awaiting approval,
  retention-due, archived, held) as the page's stat tiles. · seen in: Newforma (*Aggregate Search*),
  6.19's register stats · priority: **common** · spine: **computed page `doc_repository`** ·
  buildable now
- **Metadata-driven ("virtual") folders and taxonomy administration** — the M-Files model of
  organizing by metadata rather than location. · seen in: M-Files · priority: **differentiator** ·
  spine: parked → **13.4** · integration/later

### Bullet 2 — Document Templates & Standards ("standardized formats for charters, plans, reports, and status updates")
- **Template/standard library** — one row per reusable standard artifact: the charter template, the
  project-plan format, the status-report format, the minutes format, the lessons-learned template,
  the checklist. · seen in: Deltek PIM (*Publish a Template*; template pools), 6.19
  (`KnowledgeResource` holds "the RFP template… the how-to guide… the training deck"), Confluence
  (page templates + categories) · priority: **table-stakes** · spine: **new table
  `DocumentTemplate`** (file-backed standards) + `KnowledgeEntry.kind="template"` (content-only) ·
  buildable now
- **Template category + audience** — group standards by category so the register is browsable. ·
  seen in: Deltek PIM (template pools), Confluence (template categories), 6.19
  (`resource_type`/`audience`) · priority: **table-stakes** · spine: `category` choice on
  `DocumentTemplate` · buildable now
- **Publish/retire with a version** — a template carries a version and an active flag; retiring one
  keeps it readable but off the "start from" list. · seen in: Deltek PIM (publish + version
  comments), 6.19 (`is_featured` shelf / `status`) · priority: **common** · spine:
  `version`/`is_active` columns + verb · buildable now
- **Format lock / branding enforcement** — the standard cannot be edited into a non-standard. · seen
  in: Deltek PIM ("locked formatting") · priority: **differentiator** · spine:
  `format_locked` flag *documented as an intent*, not enforced · integration/later (**13.1** owns
  authoring)
- **Generate a document FROM a template with project merge fields** — the engine that stamps
  project name/code/date into the standard and files the result. · seen in: **Deltek PIM (entity
  classes required for merging)** · priority: **differentiator** · spine: parked → **13.1** (and
  7.16 for the report formats) · integration/later

### Bullet 3 — Version Control & Check-in/Out ("revision history, comparison tools, and conflict resolution")
- **Immutable revision chain** — every upload is a new revision row (file, checksum, uploader,
  change note, timestamps); nothing is ever amended in place. · seen in: Deltek PIM (version
  numbering schemes per placeholder), SharePoint (version history), 6.19
  (`ProcurementDocumentRevision`, structural immutability) · priority: **table-stakes** · spine:
  **new table `ProjectDocumentRevision`** · buildable now
- **Only the latest APPROVED revision is current** — upload lands unapproved behind the pointer; the
  approve verb refuses a number at or below the pointer, which is the single rule that keeps the
  chain linear. · seen in: 6.19 (the invariant everything else defends), Deltek PIM (issue/approve
  cycle) · priority: **table-stakes** · spine: `is_approved` + `current_revision_no` integer
  pointer · buildable now
- **Check-out / check-in lock** — one editor at a time: check out to work, check in to publish;
  others keep reading the last published revision. · seen in: **SharePoint ("require files to be
  checked out")**, M-Files (check-in/check-out) · priority: **table-stakes** · spine:
  `is_checked_out` + `checked_out_by`/`checked_out_at` on `ProjectDocument` + POST-only
  `pdm_checkout`/`pdm_checkin` · buildable now
- **Conflict resolution = the lock + supersede** — a second upload while a lock is held is refused
  with the holder's name; a rejected revision is superseded by the next upload, never edited. · seen
  in: SharePoint/M-Files (exclusive lock semantics) · priority: **common** · spine: the lock guard
  in `clean()`/view + refusal message · buildable now
- **Revision history panel + comparison affordance** — the chain rendered newest-first with
  per-revision metadata, change notes and a side-by-side comparison of any two revisions (number,
  note, uploader, time, size, checksum summary). · seen in: SharePoint (version history + restore
  dialog), M-Files · priority: **table-stakes** · spine: the detail page's history panel + computed
  `pdv_compare` · buildable now — **explicitly NOT a document diff/redline** (13.2)
- **Rollback / restore a previous revision** — point the pointer back at an older approved revision
  by creating a NEW revision, so history is never rewritten. · seen in: SharePoint (restore adds a
  new version) · priority: **common** · spine: a `pdv_restore` verb · buildable now
- **Branching / parallel drafts / merge-back, redlining, track changes** — seen in: Purview
  (record versions), Deltek (renditions) · priority: **differentiator** · spine: parked → **13.2** ·
  integration/later
- **Retention pruning of old versions (limit versions kept)** — seen in: SharePoint (version limits)
  · priority: **common** · spine: parked → **13.9** (auto-destruction) · integration/later

### Bullet 4 — Knowledge Base & Lessons Learned ("searchable repository of past project insights, playbooks, and retrospectives")
- **Knowledge register** — one row per reusable insight: kind (lesson_learned / retrospective /
  playbook / checklist / best_practice / template / standard), summary + body, category, tags,
  author, status. · seen in: 6.19 (`KnowledgeResource`: templates, scorecards, playbooks),
  Confluence (spaces/pages + labels), M-Files ("capture and reuse knowledge") · priority:
  **table-stakes** · spine: **new table `KnowledgeEntry`** · buildable now
- **Source-project attribution** — a lesson records the project (and optionally the risk/issue/defect
  row) it came from, so the insight is traceable. · seen in: 6.19 (source links), plus the ruled
  7.5/7.6 model where `lessons_learned` is a FIELD on the row · priority: **table-stakes** · spine:
  `source_project` FK → `projects.Project` (**7.5/7.6 keep their own fields — 7.10 is the LIBRARY,
  not a second store**) · buildable now
- **Searchable library** — `icontains` over title + summary + body + tags with a real search page
  and (Ruling 6) an honest empty state. · seen in: Newforma (*Aggregate Search*), Confluence
  (advanced search), 6.19 (search copy) · priority: **table-stakes** · spine: **computed page
  `kne_search`** · buildable now
- **Reuse affordance + popular shelf** — a "use this" click counter and a featured shelf so good
  playbooks surface first; the count is a click counter, never a reconciliation. · seen in: 6.19
  (`usage_count` with `F()+1`, `is_featured` shelf) · priority: **common** · spine: `usage_count` +
  `is_featured` + a POST-only use verb · buildable now
- **Review date on a knowledge row** — content rots, so a computed `is_review_due` badge keeps it
  honest. · seen in: 6.19 (`is_review_due` computed, never stored) · priority: **common** · spine:
  `review_on` + computed property · buildable now
- **Wikis, co-authored pages, real-time editing** — seen in: Confluence (real-time editing,
  whiteboards, databases) · priority: **differentiator** · spine: parked → **13.17** (and there is
  no websocket stack in this repo) · integration/later
- **AI summaries, semantic search, recommendations** — seen in: Confluence (Rovo), M-Files (Aino) ·
  priority: **differentiator** · spine: parked → **13.5/13.6**, Module 23 · integration/later

### Bullet 5 — Document Retention & Archiving ("lifecycle policies, legal hold, and post-project archival workflows")
- **Retention intent on the row** — `retention_months` → computed `retain_until` /
  `is_retention_due`, plus a `review_on` review date. **A flag a human reads, never an action**
  (6.19's ruling, verbatim). · seen in: Purview (retention labels/periods), Preservica (retention
  schedules), 6.19 (`retention_until` + reminder window) · priority: **table-stakes** · spine:
  columns + computed properties on `ProjectDocument` · buildable now
- **Archive / unarchive as an audited Toggle verb** — `is_archived` + `archived_by`/`archived_at`;
  archived rows stay reachable through a lens and leave the live register by default. · seen in:
  Newforma (post-project archiving), 6.19 (archive idiom) · priority: **table-stakes** · spine:
  `pdm_archive` Toggle verb · buildable now
- **Legal hold that BLOCKS** — `is_legal_hold` + `hold_reason`: while held, delete and archive are
  refused in `clean()` and on the delete view; hold/release are audited verbs. · seen in:
  **Preservica (legal hold overrides retention)**, Purview (eDiscovery holds) · priority:
  **differentiator** · spine: columns + `pdm_hold`/`pdm_release` Toggle verbs · buildable now
- **Retention & Archiving board** — one computed page: totals, retention due/overdue, review due,
  archived, held, with a **Run** that raises idempotent in-app reminders (no scheduler, no mail
  worker). · seen in: Preservica (disposition review), Purview (disposition review), 6.19
  (`run_document_reminders` idempotent Run) · priority: **table-stakes** · spine: **computed page
  `doc_retention`** + a module-level reminder function · buildable now
- **Automatic destruction on expiry, immutable vault, cryptographic authenticity proofs, proof of
  deletion** — seen in: Preservica (system-level immutability, audit log, disposition proof),
  Purview (regulatory records, proof of deletion) · priority: **differentiator** · spine: parked →
  **13.9/13.14** (7.10 deletes nothing on a schedule) · integration/later
- **File-plan import / tenant-wide retention schedules as master data** — seen in: Purview (file
  plan) · priority: **common** · spine: parked → **7.19** · integration/later

---

## Recommended build scope (this pass — 5 models, 4 entity files)

Package: `models/DocumentKnowledgeManagement/` (mirroring procurement 6.19's folder name), template
slug `documentknowledge/` under `templates/projects/`. Migration `0014`. Seeder block `_docmgt`.
Route-name namespaces `pfd_`, `pdm_`, `pdv_`, `dtm_`, `kne_` (verified unused in this app).

### 1. `ProjectFolder` [PFD-] — `ProjectFolders.py` — bullet 1
`TenantNumbered`. The per-project folder tree.
- `project` FK → `projects.Project` (`related_name="doc_folders"`, CASCADE) — **required** (a project
  folder without a project is meaningless);
- `parent` self-FK → `ProjectFolder` (`related_name="children"`, CASCADE, nullable = a root folder),
  with `clean()` refusing a parent from **another project** and refusing a self/descendant cycle;
- `name`, `description` (blank), `sequence` (for stable ordering), `is_archived` +
  `archived_by`/`archived_at` (Toggle verb `pfd_archive`);
- `unique_together (tenant, project, parent, name)` so one parent cannot hold two folders of the same
  name; **the materialized `1.2.3` path and the document count are COMPUTED in the tree view**
  (the 7.2 WBS idiom), never stored;
- indexes `(tenant, project)`, `(tenant, parent)`, `(tenant, is_archived)`.
- Justified by: Deltek PIM project document sets, Newforma *File Manager*, and 7.9's own sidebar
  comment assigning "the file store, **the folders** and the VERSION HISTORY" to 7.10.

### 2. `ProjectDocument` [PDM-] — `Documents.py` — bullets 1, 3 (parent half), 5
`TenantNumbered`. The register — one row per controlled project document.
- `project` FK (required, CASCADE, `related_name="documents"`), `folder` FK → `ProjectFolder`
  (`related_name="documents"`; **Phase 2 pins PROTECT vs SET_NULL** — 6.19's delete-refusal idiom
  argues PROTECT plus an empty-folder guard);
- `title`, `document_type` (charter / plan / schedule / report / status_update / minutes /
  specification / drawing / test_result / handover / other), `classification`
  (public/internal/confidential — the `core.Document` vocabulary, reused deliberately),
  `owner` FK → AUTH_USER_MODEL (SET_NULL), `tags` (normalized CharField via a shared
  `normalize_tags` helper — 6.19's idiom, so one tag is one tag across both registers);
- `status` (draft / **expected** / in_review / approved / superseded / archived — `expected` is
  Deltek's placeholder state, which is how Ruling 1 keeps a placeholder from becoming a second
  table);
- real link FKs declared **by string**: `milestone` → `projects.ProjectMilestone` (nullable),
  `task` → `projects.ProjectTask` (nullable) — 6.19's "four real link FKs, never a GFK" ruling;
- the check-out lock: `is_checked_out`, `checked_out_by` FK → AUTH_USER_MODEL (SET_NULL),
  `checked_out_at` — all verb-written by `pdm_checkout`/`pdm_checkin` only;
- retention/hold: `retention_months` (nullable), `review_on`, `is_archived` +
  `archived_by`/`archived_at`, `is_legal_hold` + `hold_reason`;
- the pointer + search copy: `current_revision_no` (default 0 = none — **an integer pointer, never a
  circular FK**), `extracted_text` (**a denormalized SEARCH COPY**, written by exactly two writers:
  the revision-approve verb and the re-index Run);
- computed properties: `is_expected`, `is_locked`, `retain_until`, `is_retention_due`,
  `is_review_due`, `current_revision` (**filters `is_approved=True`** — 6.19's hard-won rule 5),
  `tag_list`;
- `unique_together (tenant, number)`; indexes `(tenant, project)`, `(tenant, folder)`,
  `(tenant, status)`, `(tenant, document_type)`, `(tenant, is_archived)`;
- `clean()`: a title is required for a non-expected row; a legal hold refuses archive; a
  checked-out row refuses a second check-out and refuses upload until checked in; cross-tenant
  backstop on `folder`/`milestone`/`task` (`_id` tested FIRST — the 6.19 guard).
- The create form offers **two honest paths**: create a real document by uploading **revision 1**
  (the only way a document gets bytes — the repository owns its uploads), or create an **`expected`
  placeholder** (Deltek's slot-before-the-file). **Amended at build time (2026-09-15):** an earlier
  draft offered "register an existing `core.Document`" as a third path; it was dropped because it
  needs exactly the nullable FK to `core.Document` that Ruling 2 forbids (and 6.19 ships no such
  link either). The two shelves stay distinct BY DESIGN, and the document detail page links to
  **7.9's share register** (`dsh_list?project=…`) as the sibling shelf rather than pretending one
  row can be on both.

### 3. `ProjectDocumentRevision` [PDV-] — `Revisions.py` — bullet 3
`TenantOwned` child — no number of its own (6.19's shape: the revision is identified by its parent's
number plus `revision_no`).
- `document` FK → `ProjectDocument` (`related_name="revisions"`, CASCADE), `revision_no`
  (PositiveSmallInteger), `file` (FileField `projects/documents/%Y/%m/`, extension allow-list + size
  cap), `checksum` (SHA-256 of the stored bytes, streamed a chunk at a time — 6.19's helper),
  `change_note` (**the ONLY column editable after creation**), `is_approved` + `approved_by` /
  `approved_at`, `extracted_text` (**the TEXT OF RECORD**) + `extraction_note`;
- `unique_together (tenant, document, revision_no)`; index `(tenant, document)`;
- immutability is **structural**, not a `save()` guard: no edit url, no edit view, no edit template,
  every column but `change_note` is `editable=False`, and the only form is the create-path upload
  form;
- verbs: `pdv_approve` (refuses `revision_no <= current_revision_no` **inside** the parent row lock,
  then stamps the row, moves the pointer, copies `extracted_text` up to the parent and lifts the
  parent's status on first approval), `pdv_restore` (rolls forward from an older approved revision by
  creating a NEW revision), `pdv_reindex` (re-runs extraction);
- **no second timestamp column**: `TenantOwned.created_at` IS the upload moment;
- delete is permitted only for an **unapproved, non-current** revision, and the guard runs under the
  parent row lock (6.19 rule 8).

### 4. `DocumentTemplate` [DTM-] — `Templates.py` — bullet 2
`TenantNumbered`. The standards library — **file-backed standards only**; content-only standards live
in `KnowledgeEntry.kind="template"` (Ruling 4).
- `name`, `category` (charter / plan / schedule / report / status_update / minutes / register /
  checklist / other), `document_type` (the same vocabulary as `ProjectDocument`, so a project can
  offer "start from a template" per type), `description`, `version` (CharField — the Deltek
  "publish" version), `file` (FileField, extension allow-list), `is_active` (publish/retire Toggle
  `dtm_publish`), `is_format_locked` (**documented as an INTENT only** — nothing in this pass
  enforces authorship, and no page may claim it does), `owner` FK → AUTH_USER_MODEL (SET_NULL),
  `review_on`;
- **tenant-wide, with no project FK** — a standard belongs to the PMO, not to one project (the
  deliberate contrast with `ProjectDocument.project`, which is required);
- `unique_together (tenant, name, version)`; indexes `(tenant, category)`, `(tenant, is_active)`.

### 5. `KnowledgeEntry` [KNE-] — `Knowledge.py` — bullet 4 (and content-only bullet 2)
`TenantNumbered`. The reusable-insight library.
- `title`, `kind` (lesson_learned / retrospective / playbook / checklist / best_practice / template /
  standard), `summary` (CharField), `body` (TextField), `category`, `tags` (the SAME normalizer the
  document register uses), `source_project` FK → `projects.Project` (nullable, SET_NULL — an insight
  outlives the project), `owner` FK → AUTH_USER_MODEL, `status` (draft / published / retired),
  `review_on`, `usage_count` (incremented with an atomic `F()+1` inside the `kne_use` verb — a click
  counter, never a metric and never an audit trail), `is_featured` (the shelf, **never a
  permission** — 6.19's PKR docstring);
- optional `document` FK → `ProjectDocument` (nullable) for the artifact behind a playbook — **no
  FileField here**, so a scorecard or deck goes through the repository's allow-list, size cap,
  checksum, text read and revision chain ("one artifact, one place, one history"), with the 6.19
  cross-tenant `clean()` guard;
- ordering `["-is_featured", "-created_at", "-id"]` — the `-id` tiebreak is **load-bearing** for
  deterministic paging (6.19's PKR note);
- `unique_together (tenant, number)`; indexes `(tenant, kind)`, `(tenant, status)`,
  `(tenant, is_featured)`.

**Computed pages (no tables):** `doc_repository` (overview stat tiles + the register lens),
`doc_retention` (retention & archiving board + the idempotent reminder Run), `kne_search` (library
search). **Sidebar mapping (five bullets, six registers — state it once, explicitly, in Phase 2):**
bullet 1 → `pdm_list` with `pfd_list` as the extra live leaf (the 7.8/7.9 idiom), bullet 2 →
`dtm_list`, bullet 3 → `pdv_list`, bullet 4 → `kne_list`, bullet 5 → `doc_retention`.

---

## Belongs to sibling sub-modules (parked, not scoped here)

| Feature | Owner |
|---|---|
| Access levels, single-editor claim, share/revoke ("who may do what with a document") | **7.9 `DocumentShare`** — already shipped; 7.10 shows it as a read-only lens |
| Whatever a project *is* (charter, stakeholder RACI, kickoff attestation) | **7.1** |
| The WBS node, the schedule baseline, the milestone gate | **7.2** — 7.10 only LINKS a document to a milestone/task |
| Capacity, bookings, timesheet actuals | **7.3** |
| Budgets, CCA, EVM, expenses | **7.4** — a document has no money column |
| Risk register, issue log, response actions | **7.5** — `lessons_learned` stays a FIELD on its rows |
| Quality plans, inspections, defects | **7.6** — `lessons_learned` stays a FIELD on its rows |
| Requirements, scope items, change requests | **7.7** |
| Task execution, checklists, blocking, boards | **7.8** |
| Client/external portal visibility and deliverable sharing with outsiders | **7.14** |
| Status-report and dashboard *formats* as generated reports | **7.16** |
| Notification/reminder RULES, escalation and recurrence engines | **7.17** — 7.10's Run raises rows only |
| Webhooks/API for document events; external repository sync | **7.18** |
| Tenant-wide retention schedules / file-plan master data, doc-type taxonomies, report formats | **7.19** |
| Contracts, contract templates and contract revision history | **crm 1.9** (`ContractDocument` + `DocumentVersion` + `DocTemplates` [TPL-]) — already built, **untouched** |
| HR letters, HR knowledge articles/categories, employee documents | **hrm** (`DocumentRequest` [DOCREQ-], `Document` [EDOC-], `KnowledgeBase` [KB-], `KnowledgeArticle` [KBA-], `KbCategories` [KBC-]) — already built, **untouched** |
| Procurement documents, procurement policies, procurement knowledge resources | **procurement 6.19** (`ProcurementDocument` [PDOC-], `ProcurementDocumentRevision`, `ProcurementPolicy` [PPOL-], `KnowledgeResource` [PKR-]) — the mirror image, **not re-declared** |
| The enterprise DMS: authoring & co-editing (13.1), branching/redlining/rollback (13.2), approval workflow designer + e-signature (13.3), storage deployment (13.4), semantic search/auto-tagging (13.5/13.6), permission matrices/DRM/watermarking (13.7), retention auto-destruction + legal-hold enforcement (13.9/13.14), wikis (13.17) | **Module 13** |

## Deferred (later passes / integrations)

1. **Document diff / redline / track-changes comparison** — 7.10's comparison is *metadata*
   side-by-side (number, note, uploader, time, size, checksum), never a rendered text diff; real
   redlining is 13.2's.
2. **Template merge-fields generation** (create a project document *from* a template with the
   project's data stamped in) — Deltek's "entity classes required for merging"; parked to 13.1
   because it needs an authoring engine that does not exist here.
3. **Multi-file renditions per document** (Deltek's Word + TIFF + PDF against one placeholder) —
   this pass keeps one file per revision; renditions would be a child table and are deferred.
4. **Notifying by email / scheduling reminders** — the Run raises in-app notifications only (no
   scheduler, no mail worker in this repo); delivery channels and rules are 7.17's.
5. **Automatic retention destruction, immutable vault, proof-of-deletion artefacts** — 13.9/13.14.
6. **Semantic/vector search, OCR of scanned images, auto-tagging** — 13.5/13.6 and Module 23. 7.10's
   extraction reads a text layer only and says so.
7. **Bulk folder/placeholder import (CSV/TXT)** — Deltek supports it; deferred until the register
   shape is stable.
8. **Document sets / baskets and "share by email"** — Deltek's transmittal-adjacent affordance;
   parked to 7.14 / Module 13.
9. **Per-project document numbering schemes** (Deltek assigns each placeholder a version numbering
   scheme) — deferred: 7.10 uses the app-wide `TenantNumbered` sequence plus a per-document
   `revision_no`; a configurable scheme is 7.19's master data.

---

## Verification notes (how the repo-state claims above were checked)

- `apps/core/navigation.py` read directly: nine `"7.N":` keys (lines 1704-1858), and the file's own
  comments at 1841-1844 and 1859-1874 read in full (they carry the deliberate-omission rulings).
- `apps/core/models/Document.py` read in full (28 lines) — the GFK, the flat `version` CharField,
  the classification vocabulary, and the docstring naming the future DMS layer.
- `apps/projects/models/CollaborationCommunication/DocumentShares.py` (`DocumentShare`,
  `NUMBER_PREFIX = "DSH"`, `document` FK → `core.Document`, `related_name="project_shares"` —
  line 28) and **every** `NUMBER_PREFIX` in `apps/projects/models/**` enumerated.
- `grep NUMBER_PREFIX` across `apps/**` for `PFD|PDM|PDV|DTM|KNE|PDT|DTMPL` → **no hits** (free).
  The taken list came from the same sweep: `PDOC`, `DOCREQ`, `EDOC`, `KB`, `KBA`, `KBC`, `TPL`,
  `LSN`, `ARL`, `RTV`, `DSH`, `CHN`, `CHM`, `MTG`, `AGI`, `MAIT`, `NTF`, `RSP`, `RAL`, `RTE`…
- `apps/procurement/models/DocumentKnowledgeManagement/{Documents,Revisions,KnowledgeResources}.py`
  read in full, plus `.claude/skills/procurement/SKILL.md`'s `## 6.19` section — the source of every
  "6.19 rule n" cited above (the revision-chain invariants, the `extracted_text` search-copy ruling,
  the `usage_count`/`is_featured` rulings, the delete-refusal rule).
- `apps/crm/models/DocumentContract/DocumentVersions.py` and
  `apps/hrm/models/RequestManagement/Documentrequest.py` read in full to confirm the sibling
  collisions are real and to draw the naming boundary.
- `NavERP.md` `### 7.10` bullets (lines 1216-1221), the Module 13 heading list (line 1980+), and
  `### 6.19`'s position (line 1142) read from the catalog.
- `venv\Scripts\python.exe manage.py makemigrations --check --dry-run` → *No changes detected*, so
  there is no un-absorbed drift and **`0014` is the correct claim**.
- **Environment caveat for the build phase:** XAMPP MariaDB was **not running** in this session
  (port 3306 closed, no `mysqld` process), so `migrate` / `seed_projects --flush` / the live smoke
  sweep need MySQL started first. The pytest suite is unaffected — it runs on SQLite in-memory via
  `config.settings_test`.