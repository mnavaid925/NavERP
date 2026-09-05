"""Procurement 6.17 Risk & Compliance Management - the audit seal chain (NavERP.md bullet 3).

**Audit Trail & Logging** bullet: *"Tamper-proof logs of every action taken in the system for
audit purposes."*

---

## Read this before you read the code: what this DOES and DOES NOT claim

``core.AuditLog`` is a normal table. It has no hash column, no sequence number, no verification
and nothing in the database preventing an ``UPDATE`` or a ``DELETE`` - an administrator with a SQL
prompt can rewrite any row in it, and nothing here changes that. So this module never uses the
word "tamper-proof" on a page, and neither should anything built on it.

What it does provide is **tamper EVIDENCE**: a SHA-256 chain over id-keyed ranges that makes an
after-the-fact modification, deletion or insertion **detectable, and locates it**. Detectable is a
much weaker claim than impossible, and the difference is the whole design:

* a seal proves the sealed range is **unchanged since it was sealed** - it can say nothing about
  what happened to a row *before* the first seal covered it, including a row deleted before then,
  which leaves no trace at all;
* the ``last_verify_*`` stamps are ordinary columns and are exactly as rewritable as the log. They
  record that somebody pressed Verify and what came back; the PROOF is re-running the verification,
  which is why the button is on every seal;
* real append-only storage (WORM volumes, a database with row-level immutability, streaming every
  entry off-box to a SIEM) is infrastructure, and it is out of scope here. This is the honest
  application-layer half of that control, not a substitute for it.

``TAMPER_NOTE`` below is that paragraph in one sentence, and it is rendered on the trail page, the
seal register and every seal's detail page. A security control people wrongly believe in is worse
than no control, so the limits ship with the feature rather than in a doc nobody opens.

## Why the ranges are keyed by ID and never by time

A time-keyed window has a late-arrival hole. A row that COMMITS after a window was sealed but
carries an ``at`` inside it falls between the two seals and is checked by neither. ``AuditLog.id``
is a monotonic autoincrement, so an id-keyed range has no such hole: whatever a row's ``at`` says,
its id is above every id already sealed, so it lands in the NEXT seal and is covered exactly once.

That is also why ``period_start`` / ``period_end`` are labelled as the first and last entry of the
range rather than "from" and "to": they are DERIVED metadata for humans, taken in id order, and a
back-dated row can legitimately make them read out of order. **The id range is the authority.**

## Why there is no edit route and no delete route (a documented CRUD deviation)

The CRUD-completeness rule in CLAUDE.md says every model with a list page gets edit and delete.
This model deliberately ships with **neither**, and it is a decision rather than an omission:

* a seal whose digest can be edited proves nothing - "the digest matches" would only mean the last
  person to press Edit made it match; and
* deleting a seal breaks exactly the chain the seal exists to protect, and it is the single move
  somebody covering their tracks would make first.

So the register has View only, the model has no form field that can reach a digest, and
``AuditSealForm`` carries ``note`` alone. In-repo precedent for evidence-shaped models that ship
without the full CRUD set: ``CostForecast`` (6.15) has no edit route, and ``InvoiceMatchVariance``
(6.13) is evidence rather than a record. The reason is repeated on the pages themselves so that a
reviewer reads it as a decision.

## Zero ``core`` migrations

Nothing here adds a column to ``core.AuditLog``. The seal is a 6.17-owned table that POINTS AT id
ranges of that table, which is what lets a procurement sub-module ship this while other sessions
are building against the same checkout.

## The canonical serialisation is PINNED

``canonical_line`` is frozen (contract / todo.md 4e). Changing so much as a separator silently
invalidates every seal ever taken - they would all verify as "broken" with no tampering whatever,
which is the one failure mode that would make people stop trusting a green result. If a future
version of the serialisation is ever needed, it goes in beside this one keyed off ``algorithm``,
never on top of it.
"""
import hashlib
import json

from apps.procurement.models._base import *  # noqa: F401,F403
# Sibling entity of this SAME sub-package: imported as a MODULE so the ten-year retention basis
# has one definition. Only the NUMBER is shared - the sentence below is about audit entries, and
# reusing the screening register's wording verbatim would put a claim about screening records on
# a page that holds none.
from apps.procurement.models.RiskComplianceManagement.Screenings import RETENTION_YEARS


#: The ``prev_digest`` of the first seal in a workspace's chain. 64 zeroes is not a hash of
#: anything - it is the documented "there was nothing before this" marker, and a seal claiming
#: genesis while an older seal exists is reported as a broken link.
GENESIS_DIGEST = "0" * 64

#: Stored on every seal so a future algorithm change is a NEW value beside this one, never a
#: silent re-interpretation of digests already taken.
ALGORITHM = "sha256"

#: Ceiling on how many entries ONE seal covers. Applied as a SQL ``LIMIT`` (a queryset slice), so
#: the guard costs the same whether the unsealed backlog is 10 rows or 10 million - a cap that had
#: to load everything to discover it was over the cap would be the very payload it exists to
#: prevent (L40 1). Hitting the cap is not an error: the seal covers the first ``MAX_SEAL_ROWS``
#: entries, the message says so, and the next seal continues from there.
MAX_SEAL_ROWS = 50000

#: Hex characters kept per row in ``row_fingerprints``. 16 hex = 64 bits, which is a LOCATOR, not
#: the proof - see the field's own comment.
FINGERPRINT_CHARS = 16

#: How many links the trail page and the register show. The chain itself is not truncated; the
#: display window is.
CHAIN_STATUS_LIMIT = 12

#: How far back ``verify_chain`` walks. Bounded for the same reason as everything else here.
CHAIN_WALK_LIMIT = 500

#: Badge class per chain-link state. theme.css ships badge-green / badge-red / badge-amber /
#: badge-info / badge-muted / badge-slate ONLY - a semantic badge-success renders completely
#: unstyled while passing every test (L33).
CHAIN_STATE_CSS = {
    "verified": "badge-green",
    "unverified": "badge-amber",
    "broken": "badge-red",
    "unlinked": "badge-red",
}

CHAIN_STATE_LABEL = {
    "verified": "Verified",
    "unverified": "Not verified",
    "broken": "Broken",
    "unlinked": "Link broken",
}

#: Printed on the trail, the register and every seal. Same ten-year basis as the screening
#: register (one constant, imported), different sentence - this one is about audit entries.
RETENTION_NOTE = (
    f"Audit entries are retained for {RETENTION_YEARS} years and nothing here deletes them: this "
    f"module only reads the trail and seals ranges of it. Removing audit evidence is a deliberate "
    f"act at the database, not a scheduled job, and a seal is what makes that act visible."
)

#: The honesty sentence. Rendered verbatim on every page this entity ships.
TAMPER_NOTE = (
    "This trail is tamper-EVIDENT, not tamper-proof. The log is an ordinary database table with "
    "no immutability of its own, so a seal cannot stop a row being changed or deleted - it makes "
    "the change DETECTABLE afterwards, and names the entry it happened to. A seal proves its "
    "range is unchanged since it was sealed; it can say nothing about a row altered before the "
    "first seal covered it. Append-only storage and off-box log streaming are infrastructure "
    "controls and are not implemented here."
)


class AuditSeal(TenantNumbered):
    """A SHA-256 seal over one id-keyed range of this workspace's ``core.AuditLog``.

    Each seal chains onto the one before it (``chain_digest = H(prev_digest : digest)``), so
    altering any sealed entry breaks that seal and every claim of continuity after it.

    **No edit route and no delete route** - see the module docstring: a seal whose digest can be
    edited proves nothing, and deleting a seal breaks the chain it exists to protect. Every digest
    column is ``editable=False`` and off the form; ``note`` is the only operator-supplied field.
    """

    NUMBER_PREFIX = "ASL"

    GENESIS_DIGEST = GENESIS_DIGEST
    ALGORITHM = ALGORITHM
    MAX_SEAL_ROWS = MAX_SEAL_ROWS
    FINGERPRINT_CHARS = FINGERPRINT_CHARS
    CHAIN_STATUS_LIMIT = CHAIN_STATUS_LIMIT
    CHAIN_WALK_LIMIT = CHAIN_WALK_LIMIT
    RETENTION_YEARS = RETENTION_YEARS
    RETENTION_NOTE = RETENTION_NOTE
    TAMPER_NOTE = TAMPER_NOTE

    # -- coverage: an ID range, never a time range (module docstring) ----------------------------
    from_log_id = models.BigIntegerField(
        editable=False, help_text="Lowest core.AuditLog id covered by this seal")
    to_log_id = models.BigIntegerField(
        editable=False, help_text="Highest core.AuditLog id covered by this seal")

    # DERIVED metadata, in id order, for humans. Not the authority on coverage.
    period_start = models.DateTimeField(editable=False)
    period_end = models.DateTimeField(editable=False)
    row_count = models.PositiveIntegerField(default=0, editable=False)

    # -- the evidence ----------------------------------------------------------------------------
    digest = models.CharField(max_length=64, editable=False)
    prev_seal = models.ForeignKey(
        "self", on_delete=models.SET_NULL, null=True, blank=True, editable=False,
        related_name="next_seals")
    prev_digest = models.CharField(max_length=64, blank=True, editable=False)
    chain_digest = models.CharField(max_length=64, editable=False)
    algorithm = models.CharField(max_length=16, default=ALGORITHM, editable=False)

    #: Per-entry ``[id, fingerprint]`` pairs, in id order.
    #:
    #: **This list is a LOCATOR, not the proof.** The 256-bit ``digest`` above is what proves the
    #: range is unchanged; these truncated hashes are what let ``verify()`` say *which* entry
    #: changed instead of only that something did. A verifier that reports "broken" without saying
    #: where is unusable in the one situation it exists for - somebody has to go and look.
    #:
    #: Localisation is impossible without per-entry evidence (an aggregate hash cannot be
    #: attributed), so this column is the price of that requirement. It is bounded by exactly the
    #: same ``MAX_SEAL_ROWS`` ceiling as the digest computation, and every list queryset
    #: ``.defer()``s it so the register never loads it. A locator collision (64 bits) costs an
    #: attacker only the LOCATION of their edit, never the detection: the 256-bit digest still
    #: fails and verify() falls back to "the changed entry could not be located".
    row_fingerprints = models.JSONField(default=list, blank=True, editable=False)

    # -- who / when ------------------------------------------------------------------------------
    sealed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, editable=False,
        related_name="procurement_audit_seals")
    sealed_at = models.DateTimeField(auto_now_add=True)
    note = models.CharField(
        max_length=255, blank=True,
        help_text="Why this seal was taken - the only field anybody types on this record")

    # -- verification stamps: a record of the last check, NOT proof of anything ------------------
    last_verified_at = models.DateTimeField(null=True, blank=True, editable=False)
    last_verify_ok = models.BooleanField(null=True, editable=False)
    last_verify_detail = models.CharField(max_length=255, blank=True, editable=False)

    class Meta:
        ordering = ["-to_log_id", "-id"]
        unique_together = (("tenant", "number"),)
        indexes = [
            models.Index(fields=["tenant", "to_log_id"], name="prc_asl_tnt_tolog_idx"),
            models.Index(fields=["tenant", "sealed_at"], name="prc_asl_tnt_sealed_idx"),
        ]

    def __str__(self):
        return f"{self.number or 'ASL'} · {self.row_count} rows · {self.digest[:12]}"

    # -- the pinned serialisation ----------------------------------------------------------------

    @staticmethod
    def canonical_line(row):
        """One ``core.AuditLog`` row as the exact string that gets hashed. **PINNED.**

        Changing anything about this - a separator, a field, the order, the JSON flags - makes
        every seal ever taken read as broken with no tampering whatever, which is the one failure
        mode that would make people stop trusting a green result. ``sort_keys=True`` with fixed
        separators is what makes the ``changes`` JSON canonical (dict order is not stable across a
        round trip through the database), and ``default=str`` stops a ``Decimal`` or a ``date``
        inside ``changes`` raising instead of hashing.

        The one guard beyond the pin: ``at`` is read defensively. It is ``auto_now_add`` and is
        never NULL on a real row, so this changes the serialisation of nothing that exists - but
        somebody rewriting the table could NULL it, and an ``AttributeError`` there would crash
        the verifier rather than failing the seal, which is the same as disabling verification.
        """
        return "|".join([
            str(row.id),
            row.at.isoformat() if row.at else "",
            str(row.user_id or ""),
            str(row.content_type_id or ""),
            str(row.object_id or ""),
            row.action or "",
            row.target or "",
            json.dumps(row.changes, sort_keys=True, separators=(",", ":"), default=str),
        ])

    @classmethod
    def row_fingerprint(cls, row):
        """The truncated per-row hash stored in ``row_fingerprints``. A locator, not the proof."""
        return hashlib.sha256(
            cls.canonical_line(row).encode("utf-8")).hexdigest()[:FINGERPRINT_CHARS]

    @classmethod
    def compute_digest(cls, rows):
        """SHA-256 over ``rows`` in ASCENDING ID ORDER. **PINNED** alongside ``canonical_line``.

        One hash object updated per row (the line, then a newline), so the cost is linear in the
        rows and the memory is constant.
        """
        digest = hashlib.sha256()
        for row in rows:
            digest.update(cls.canonical_line(row).encode("utf-8"))
            digest.update(b"\n")
        return digest.hexdigest()

    @staticmethod
    def chain_value(prev_digest, digest):
        """``h_i = H(h_i-1 : d_i)`` - what makes the seals a CHAIN rather than a pile."""
        return hashlib.sha256(f"{prev_digest}:{digest}".encode("utf-8")).hexdigest()

    # -- sealing ---------------------------------------------------------------------------------

    @classmethod
    def seal_now(cls, tenant, user, note=""):
        """Seal every audit entry written since the last seal. Returns ``(seal, message)``.

        ``seal`` is ``None`` when nothing was sealed and the message says why. **An empty range is
        refused**: a seal covering no rows is chain spam that dilutes the register and proves
        nothing, so pressing the button twice in a row is a no-op with a sentence on it.

        The range is ``id > prev.to_log_id``, capped at ``MAX_SEAL_ROWS`` by a queryset slice (a
        SQL ``LIMIT``). Both ends are read inside one ``transaction.atomic()`` with the previous
        seal under ``select_for_update()``, so two people pressing Seal at the same moment cannot
        produce two seals covering the same rows. (The very first seal of a workspace has no row
        to lock; two simultaneous first seals would both succeed, and the second is then reported
        as an unlinked genesis by ``chain_links`` rather than passing silently.)

        **Tenant-scoped in both directions.** The range is ``filter(tenant=tenant, ...)``, so one
        workspace's seal never covers another's entries even though their ids interleave in the
        same table - and because ids are monotonic, another workspace writing later can never land
        inside an already-sealed range either.
        """
        from apps.core.models import AuditLog

        if tenant is None:
            return None, "Select a tenant workspace before sealing the audit trail."

        with transaction.atomic():
            prev = (cls.objects.select_for_update()
                    .filter(tenant=tenant).order_by("-to_log_id", "-id").first())
            last_id = prev.to_log_id if prev else 0
            rows = list(AuditLog.objects
                        .filter(tenant=tenant, id__gt=last_id)
                        .order_by("id")[:MAX_SEAL_ROWS])
            if not rows:
                if prev is None:
                    return None, ("There is nothing to seal: this workspace has no audit entries "
                                  "yet. Seal once there is activity to cover.")
                return None, (f"No new audit rows since {prev.number}. An empty seal would prove "
                              f"nothing, so none was created.")

            prev_digest = (prev.chain_digest if prev else "") or GENESIS_DIGEST
            digest = cls.compute_digest(rows)
            seal = cls(
                tenant=tenant,
                from_log_id=rows[0].id,
                to_log_id=rows[-1].id,
                period_start=rows[0].at,
                period_end=rows[-1].at,
                row_count=len(rows),
                digest=digest,
                prev_seal=prev,
                prev_digest=prev_digest,
                chain_digest=cls.chain_value(prev_digest, digest),
                algorithm=ALGORITHM,
                row_fingerprints=[[row.id, cls.row_fingerprint(row)] for row in rows],
                sealed_by=user if getattr(user, "is_authenticated", False) else None,
                note=(note or "").strip()[:255],
            )
            seal.save()

        capped = ""
        if seal.row_count >= MAX_SEAL_ROWS:
            capped = (f" That is the {MAX_SEAL_ROWS}-entry ceiling for a single seal - press Seal "
                      f"again to cover the rest.")
        return seal, (f"Sealed {seal.row_count} entries as {seal.number}, covering "
                      f"#{seal.from_log_id} to #{seal.to_log_id}.{capped}")

    # -- verification ----------------------------------------------------------------------------

    def verify(self, stamp=True):
        """Re-read the sealed range, re-hash it, and report ``(ok, detail)``.

        On failure ``detail`` **names the first offending entry id** - modified, deleted or
        inserted - because "this seal is broken" without a location is not actionable: somebody
        has to go and look at a row, and this says which one.

        Read-mostly by design: the only write is the three ``last_verify_*`` stamps, and they go
        through a targeted ``.update()`` so verifying never touches ``updated_at`` and can never
        re-run number allocation. Pass ``stamp=False`` to check without writing at all.

        The read is capped at ``MAX_SEAL_ROWS + 1``: the range should hold exactly ``row_count``
        rows, and the one extra is what turns "somebody inserted rows into a sealed range" into a
        reported difference instead of an unbounded read.
        """
        from apps.core.models import AuditLog

        rows = list(AuditLog.objects
                    .filter(tenant_id=self.tenant_id,
                            id__gte=self.from_log_id, id__lte=self.to_log_id)
                    .order_by("id")[:MAX_SEAL_ROWS + 1])
        ok, detail = self._compare(rows)
        if stamp:
            now = timezone.now()
            detail = detail[:255]
            type(self).objects.filter(pk=self.pk).update(
                last_verified_at=now, last_verify_ok=ok, last_verify_detail=detail)
            self.last_verified_at = now
            self.last_verify_ok = ok
            self.last_verify_detail = detail
        return ok, detail

    def _compare(self, rows):
        """The three independent checks, ordered so the message names the most useful one."""
        digest = self.compute_digest(rows)
        chain = self.chain_value(self.prev_digest or GENESIS_DIGEST, digest)
        link_ok, link_detail = self.link_state()

        if digest != self.digest:
            return False, self._difference_detail(rows)
        if chain != self.chain_digest:
            # The entries still hash correctly, so the mismatch is in the SEAL ROW itself.
            return False, (f"The {len(rows)} sealed entries are intact, but {self.number}'s own "
                           f"chain digest does not match them: the seal record has been altered.")
        if not link_ok:
            return False, link_detail
        return True, (f"Verified: {self.row_count} entries ({self.range_label}) still hash to the "
                      f"sealed digest.")

    def _difference_detail(self, rows):
        """Name the FIRST offending entry, or say plainly that it could not be located."""
        located = self._first_difference(rows)
        delta = self.row_count - len(rows)
        if located is not None:
            kind, log_id = located
            if kind == "modified":
                return (f"BROKEN: audit entry #{log_id} has been MODIFIED since {self.number} was "
                        f"sealed.")
            if kind == "missing":
                return (f"BROKEN: audit entry #{log_id} has been DELETED since {self.number} was "
                        f"sealed ({delta} of {self.row_count} sealed entries are missing).")
            return (f"BROKEN: audit entry #{log_id} was INSERTED into the sealed range after "
                    f"{self.number} was sealed.")
        if delta > 0:
            return f"BROKEN: {delta} of {self.row_count} sealed entries are missing."
        if delta < 0:
            return (f"BROKEN: {-delta} entries have appeared inside the sealed range since "
                    f"{self.number} was sealed.")
        return (f"BROKEN: the {len(rows)} entries in {self.range_label} no longer hash to the "
                f"sealed digest; the changed entry could not be located.")

    def _first_difference(self, rows):
        """``(kind, log_id)`` for the first divergence, or ``None``.

        Walks the sealed ``[id, fingerprint]`` list and the live rows together in id order, which
        distinguishes the three tamper shapes from one another:

        * ``modified`` - same id, different fingerprint
        * ``missing``  - a sealed id the live range no longer holds
        * ``inserted`` - a live id the seal never covered

        Returns ``None`` when the seal carries no fingerprints, so a caller must treat ``None`` as
        "could not locate", never as "nothing wrong" - the digest comparison is what decides.
        """
        sealed = self.row_fingerprints or []
        if not sealed:
            return None
        index = position = 0
        while index < len(sealed) and position < len(rows):
            pair = sealed[index]
            sealed_id, sealed_fp = int(pair[0]), pair[1]
            row = rows[position]
            if row.id == sealed_id:
                if self.row_fingerprint(row) != sealed_fp:
                    return "modified", sealed_id
                index += 1
                position += 1
            elif row.id > sealed_id:
                return "missing", sealed_id
            else:
                return "inserted", row.id
        if index < len(sealed):
            return "missing", int(sealed[index][0])
        if position < len(rows):
            return "inserted", rows[position].id
        return None

    def link_state(self):
        """``(ok, detail)`` for this seal's link to the one before it. No audit-log reads.

        Catches the two ways the CHAIN breaks without any entry changing: a seal deleted out of
        the middle, and a stored ``prev_digest`` that no longer matches what it points at.
        """
        expected = self.prev_digest or GENESIS_DIGEST
        if self.prev_seal_id is None:
            if expected != GENESIS_DIGEST:
                return False, (f"{self.number} carries a previous digest but points at no previous "
                               f"seal: the seal it chained onto has been deleted.")
            return True, f"{self.number} is the first seal in this workspace's chain."
        try:
            prev = self.prev_seal
        except type(self).DoesNotExist:  # a dangling id left by a raw DELETE
            prev = None
        if prev is None:
            return False, (f"The seal {self.number} chains onto is gone: the chain cannot be "
                           f"followed past this point.")
        if prev.chain_digest != expected:
            return False, (f"Chain link broken: {prev.number}'s chain digest no longer matches the "
                           f"copy stored in {self.number}.")
        return True, f"Chains onto {prev.number}."

    # -- chain-wide views (cheap: seals only, never the log) --------------------------------------

    @classmethod
    def chain_links(cls, tenant, limit=CHAIN_STATUS_LIMIT):
        """The chain as display rows, newest first. **One query. Never reads ``core.AuditLog``.**

        This is what the ``chain_status`` context key renders, and it is deliberately CHEAP:
        re-hashing every sealed entry on every page render would make the trail unopenable on a
        large log. It reports two different kinds of fact and the pages label them as such - the
        STRUCTURAL link between seals, which it checks here and now, and the stored result of the
        last full verification, which is the record of a check somebody ran, not a check.

        ``limit + 1`` rows are fetched so that every RETURNED row has an older neighbour to check
        its link against; the extra row is a reference only and is not returned.

        ROW-DICT CONTRACT (L41 1) - every entry carries EXACTLY::

            {"pk":            int,
             "number":        str,            # ASL-00003
             "row_count":     int,
             "range":         str,            # "#101 - #240"
             "sealed_at":     datetime,
             "linked":        bool,           # structural link to the previous seal holds
             "link_detail":   str,            # the sentence explaining `linked`
             "verified":      bool | None,    # last_verify_ok; None = never verified
             "verified_at":   datetime | None,
             "verify_detail": str,
             "state":         str,            # "verified"|"unverified"|"broken"|"unlinked"
             "state_css":     str,            # a real theme.css badge class (L33)
             "state_label":   str,
             "digest_short":  str}            # first 12 chars of chain_digest
        """
        if tenant is None:
            return []
        window = list(cls.objects.filter(tenant=tenant)
                      .defer("row_fingerprints")
                      .order_by("-to_log_id", "-id")[:limit + 1])
        links = []
        for index, seal in enumerate(window[:limit]):
            older = window[index + 1] if index + 1 < len(window) else None
            linked, link_detail = seal._link_state_against(older)
            if not linked:
                state = "unlinked"
            elif seal.last_verify_ok is False:
                state = "broken"
            elif seal.last_verify_ok is True:
                state = "verified"
            else:
                state = "unverified"
            links.append({
                "pk": seal.pk,
                "number": seal.number,
                "row_count": seal.row_count,
                "range": seal.range_label,
                "sealed_at": seal.sealed_at,
                "linked": linked,
                "link_detail": link_detail,
                "verified": seal.last_verify_ok,
                "verified_at": seal.last_verified_at,
                "verify_detail": seal.last_verify_detail,
                "state": state,
                "state_css": CHAIN_STATE_CSS.get(state, "badge-muted"),
                "state_label": CHAIN_STATE_LABEL.get(state, "Unknown"),
                "digest_short": (seal.chain_digest or "")[:12],
            })
        return links

    def _link_state_against(self, older):
        """``link_state()`` using an ALREADY-FETCHED older seal, so a chain walk stays one query.

        ``older`` is the next seal down in the same ordered window, or ``None`` at the oldest end.
        A seal whose ``prev_seal_id`` is not that neighbour has had a seal removed from between the
        two, which is reported rather than glossed over.
        """
        expected = self.prev_digest or GENESIS_DIGEST
        if self.prev_seal_id is None:
            if older is not None:
                return False, (f"{self.number} claims to start the chain, but {older.number} is "
                               f"older than it: the link between them is missing.")
            if expected != GENESIS_DIGEST:
                return False, (f"{self.number} carries a previous digest but points at no previous "
                               f"seal: the seal it chained onto has been deleted.")
            return True, f"{self.number} is the first seal in this workspace's chain."
        if older is None:
            # Only reachable when the window ended before this seal's predecessor, which the
            # limit+1 fetch prevents for a RETURNED row - so in practice the predecessor is gone.
            return False, (f"The seal {self.number} chains onto is gone: the chain cannot be "
                           f"followed past this point.")
        if older.pk != self.prev_seal_id:
            return False, (f"{self.number} does not chain onto {older.number}, the seal "
                           f"immediately before it: a seal has been removed from between them.")
        if older.chain_digest != expected:
            return False, (f"Chain link broken: {older.number}'s chain digest no longer matches "
                           f"the copy stored in {self.number}.")
        return True, f"Chains onto {older.number}."

    @classmethod
    def verify_chain(cls, tenant):
        """``(ok, first_broken, detail)`` for the workspace's chain, in one query.

        Same cheap basis as :meth:`chain_links` - it checks the LINKS and reports the stored
        verification stamps. It does not re-hash the log, and the detail string never claims it
        did: a seal reads as verified here because somebody pressed Verify on it and it passed.

        ``ok`` is False only for a link that is actually broken or a stamp that actually failed. A
        seal nobody has verified yet is unknown, not broken, and the sentence says so - reporting
        "not verified" as a failure would train people to ignore the one word that matters.
        """
        links = cls.chain_links(tenant, limit=CHAIN_WALK_LIMIT)
        if not links:
            return True, None, ("No seals yet. Nothing in this workspace's audit trail is covered "
                                "by a digest, so a change to it would leave no evidence at all.")
        broken = [link for link in links if link["state"] in ("broken", "unlinked")]
        # links are newest-first, so the LAST broken entry is the oldest - where it started.
        first_broken = broken[-1] if broken else None
        newest = links[0]
        if first_broken is not None:
            why = (first_broken["link_detail"] if first_broken["state"] == "unlinked"
                   else first_broken["verify_detail"])
            return False, first_broken, (f"Chain broken at {first_broken['number']}: {why} "
                                         f"Everything sealed after it inherits the doubt.")
        unverified = [link for link in links if link["verified"] is None]
        if unverified:
            return True, None, (
                f"{len(links)} seals, every link intact, sealed through entry "
                f"#{newest['range'].rsplit('#', 1)[-1]}. {len(unverified)} of them have not been "
                f"verified since they were sealed - press Verify on a seal to re-hash its entries.")
        return True, None, (f"Chain verified through {newest['number']}: {len(links)} seals, every "
                            f"link intact and every one re-hashed since it was sealed.")

    # -- display helpers -------------------------------------------------------------------------

    @property
    def range_label(self):
        return f"#{self.from_log_id} - #{self.to_log_id}"

    @property
    def digest_short(self):
        return (self.digest or "")[:12]

    @property
    def chain_short(self):
        return (self.chain_digest or "")[:12]

    @property
    def verify_state(self):
        """``verified`` / ``broken`` / ``unverified``, from the stored stamp alone."""
        if self.last_verify_ok is True:
            return "verified"
        if self.last_verify_ok is False:
            return "broken"
        return "unverified"

    @property
    def verify_css(self):
        return CHAIN_STATE_CSS.get(self.verify_state, "badge-muted")

    @property
    def verify_label(self):
        return CHAIN_STATE_LABEL.get(self.verify_state, "Unknown")

    @property
    def fingerprint_map(self):
        """``{log_id: fingerprint}`` for the sealed range - what the detail page marks rows with."""
        return {int(pair[0]): pair[1] for pair in (self.row_fingerprints or [])}
