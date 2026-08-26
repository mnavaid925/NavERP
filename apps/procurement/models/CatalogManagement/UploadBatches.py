"""Procurement 6.9 Catalog Management — CatalogUploadBatch model.

**Supplier Catalog Hosting** bullet: a supplier's price/catalog file arrives as ONE batch row.
``validate_and_stage()`` parses it into draft-pending ``CatalogItem`` rows (the buyer approves
each one there — this model never approves on its behalf), and the batch itself is the audit
artifact: counters plus a line-numbered error log freeze exactly what happened at import time,
so nothing about the outcome has to be re-derived from the staged items later.
"""
import csv
import io
from decimal import Decimal, InvalidOperation

from apps.procurement.models._base import *  # noqa: F401,F403


class CatalogUploadBatch(TenantNumbered):
    """One uploaded supplier catalog file [CUB-] and its validation outcome.

    Lifecycle: ``received`` (file stored) → ``validated`` (good rows staged as pending_approval
    catalog items) → ``published``; or → ``rejected`` from either of the first two. Only a
    received batch edits — once validated, the batch is an immutable record of its own import.
    """

    NUMBER_PREFIX = "CUB"

    #: Extensions clean() accepts — .csv ONLY until a real XLSX/XML parser exists (the
    #: staging parser is csv.DictReader); anything else is refused before review.
    ALLOWED_EXTENSIONS = (".csv",)

    #: Hard ceiling on data rows one batch may stage — keeps a runaway file from turning
    #: one POST into a ten-minute staging storm.
    MAX_DATA_ROWS = 10_000

    #: Expected CSV headers; extra columns are ignored, missing ones reject their row.
    EXPECTED_HEADERS = ("name", "supplier_part_no", "unit_price", "uom_code", "category_text")

    STATUS_CHOICES = [
        ("received", "Received"),
        ("validated", "Validated"),
        ("published", "Published"),
        ("rejected", "Rejected"),
    ]
    #: Only a freshly received batch may be edited/replaced; validation freezes the artifact.
    EDITABLE_STATUSES = ("received",)

    party = models.ForeignKey("core.Party", on_delete=models.SET_NULL, null=True, blank=True,
                              related_name="catalog_upload_batches",
                              help_text="Supplier whose catalog this file carries")
    original_filename = models.CharField(max_length=255, blank=True)
    file = models.FileField(upload_to="procurement/catalog_uploads/%Y/%m/")
    status = models.CharField(max_length=12, choices=STATUS_CHOICES, default="received")
    validated_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
                                     null=True, blank=True,
                                     related_name="procurement_upload_batches_validated")
    validated_at = models.DateTimeField(null=True, blank=True, editable=False)
    rows_parsed = models.PositiveIntegerField(default=0, editable=False)
    rows_accepted = models.PositiveIntegerField(default=0, editable=False)
    rows_rejected = models.PositiveIntegerField(default=0, editable=False)
    error_log = models.TextField(blank=True, editable=False,
                                 help_text='Line-numbered "row N: reason" rejects from validation')
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        unique_together = ("tenant", "number")
        indexes = [
            models.Index(fields=["tenant", "status"], name="prc_catupload_tnt_status_idx"),
        ]

    # -- hygiene ----------------------------------------------------------------------------------

    def save(self, *args, **kwargs):
        if not self.original_filename and self.file and self.file.name:
            self.original_filename = self.file.name.rsplit("/", 1)[-1]
        super().save(*args, **kwargs)

    def clean(self):
        if self.file and self.file.name:
            name = self.file.name.lower()
            if not any(name.endswith(ext) for ext in self.ALLOWED_EXTENSIONS):
                raise ValidationError({"file": "CSV only (.csv) — the staging parser reads "
                                               "CSV; export Excel/XML to CSV first."})

    @property
    def is_editable(self):
        return self.status in self.EDITABLE_STATUSES

    # -- actions ----------------------------------------------------------------------------------

    def validate_and_stage(self, user):
        """Parse the CSV and stage each good row as a ``pending_approval`` supplier-product item.

        Returns ``(True, staged_count)`` on success, ``(False, reason)`` when validation cannot
        run. Bad rows are never staged: each writes one ``row N: reason`` line to ``error_log``
        and the counters carry the split — a validated batch WITH rejects stays ``validated``
        (the log carries the detail), while a fully-empty file changes nothing at all.
        """
        if self.status != "received":
            return False, f"batch is {self.get_status_display().lower()}, not received"

        # Direct module imports (never the not-yet-wired package __init__).
        from apps.procurement.models.CatalogManagement.CatalogItems import CatalogItem
        from apps.scm.models.InventoryManagement.Items import UOM

        try:
            raw = self.file.read()
        except (OSError, ValueError):
            return False, "stored file could not be read"
        try:
            text = raw.decode("utf-8-sig")
        except UnicodeDecodeError:
            return False, "file is not valid UTF-8 text"

        errors = []
        parsed = 0
        items = []
        uom_cache = {}
        for row in csv.DictReader(io.StringIO(text)):
            parsed += 1
            if parsed > self.MAX_DATA_ROWS:
                # Clean refusal, nothing staged: the batch stays received so the buyer can
                # split or reject it — a runaway file never becomes a staging storm.
                return False, (f"file exceeds the {self.MAX_DATA_ROWS:,} data-row limit "
                               f"- split it into smaller batches")
            name = (row.get("name") or "").strip()
            part_no = (row.get("supplier_part_no") or "").strip()
            price_raw = (row.get("unit_price") or "").strip()
            category_text = (row.get("category_text") or "").strip()
            uom_code = (row.get("uom_code") or "").strip()

            if not name:
                errors.append(f"row {parsed}: name is required")
                continue
            try:
                price = q2(Decimal(price_raw))
            except (InvalidOperation, ValueError):
                errors.append(f"row {parsed}: unit_price '{price_raw}' is not a number")
                continue
            if price < ZERO:
                errors.append(f"row {parsed}: unit_price cannot be negative")
                continue
            uom = None
            if uom_code:
                if uom_code not in uom_cache:
                    uom_cache[uom_code] = UOM.objects.filter(
                        tenant_id=self.tenant_id, code=uom_code).first()
                uom = uom_cache[uom_code]
                if uom is None:
                    errors.append(f"row {parsed}: unknown UOM code '{uom_code}'")
                    continue

            items.append(CatalogItem(
                tenant=self.tenant,
                source_type="supplier_product",
                status="pending_approval",
                supplier=self.party,
                name=name,
                supplier_part_no=part_no,
                base_price=price,
                uom=uom,
                currency=None,
                category_text=category_text,
            ))

        if parsed == 0:
            # A header-only (or empty) file is not a validation result — leave the batch received.
            return False, "no data rows"

        # ONE transaction for the whole staging write-out: items land together with the
        # batch's new status/counters/error-log, so a mid-way failure rolls back to a
        # coherent ``received`` batch instead of staged-orphan rows.
        with transaction.atomic():
            # Re-check under a row lock: two near-simultaneous POSTs can both pass the cheap
            # pre-parse guard above; only one may hold the lock and stage.
            locked = (CatalogUploadBatch.objects.select_for_update()
                      .filter(pk=self.pk).first())
            if locked is None or locked.status != "received":
                state = locked.get_status_display().lower() if locked else "missing"
                return False, f"batch is {state}, not received"
            for item in items:
                item.save()  # NOT bulk_create: TenantNumbered must assign each CUB-staged number

            self.status = "validated"
            self.rows_parsed = parsed
            self.rows_accepted = len(items)
            self.rows_rejected = parsed - len(items)
            self.error_log = "\n".join(errors)
            self.validated_by = user
            self.validated_at = timezone.now()
            self.save(update_fields=["status", "rows_parsed", "rows_accepted", "rows_rejected",
                                     "error_log", "validated_by", "validated_at", "updated_at"])
        return True, self.rows_accepted

    def publish(self):
        """Validated → published: the staged items are confirmed as live catalog entries."""
        if self.status != "validated":
            return False
        self.status = "published"
        self.save(update_fields=["status", "updated_at"])
        return True

    def reject(self):
        """Received/validated → rejected (e.g. wrong file entirely)."""
        if self.status not in ("received", "validated"):
            return False
        self.status = "rejected"
        self.save(update_fields=["status", "updated_at"])
        return True

    def __str__(self):
        return f"{self.number or 'CUB'} · {self.original_filename or 'catalog upload'}"
