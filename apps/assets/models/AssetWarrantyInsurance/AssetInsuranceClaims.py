from decimal import Decimal

from django.conf import settings
from django.db import models

from apps.assets.models._base import TenantNumbered


class AssetInsuranceClaim(TenantNumbered):
    """
    Asset casualty, peril loss, and insurance claim settlement lifecycle [AICL-].
    Captures fire, flood, electrical surge, machinery breakdown, and collision casualties,
    independent forensic adjusters, proof of loss submissions, salvage offsets,
    and carrier net indemnity payouts.
    """

    NUMBER_PREFIX = "AICL"

    PERIL_TYPE_CHOICES = [
        ("fire_lightning", "Fire, Smoke & Lightning Strike"),
        ("flood_water_damage", "Flood, Inundation & Pipe Burst Water Damage"),
        ("electrical_arcing_surge", "Electrical Arcing, Short Circuit & Voltage Surge"),
        ("mechanical_breakdown", "Sudden & Accidental Mechanical Breakdown"),
        ("operator_error_accidental", "Operator Error, Dropping & Accidental Impact"),
        ("theft_burglary", "Theft, Burglary & Vandalism"),
        ("windstorm_hail", "Windstorm, Tornado & Hail Destruction"),
        ("collision_impact", "Vehicle Collision & Heavy Mobile Plant Impact"),
        ("collapse_subsidence", "Structural Collapse, Landslide & Subsidence"),
    ]

    CLAIM_STATUS_CHOICES = [
        ("incident_reported", "Incident Reported (Intake)"),
        ("adjuster_assigned", "Adjuster Assigned & Inspecting"),
        ("proof_of_loss_filed", "Proof of Loss Filed & Sworn"),
        ("under_carrier_review", "Under Carrier Claims Committee Review"),
        ("approved_pending_payout", "Approved (Pending Payout Dispatch)"),
        ("settled_paid", "Settled & Indemnity Dispatched"),
        ("denied_disputed", "Denied / Under Formal Dispute"),
        ("closed", "Claim File Closed"),
    ]

    SETTLEMENT_METHOD_CHOICES = [
        ("direct_indemnity_check", "Direct Carrier Indemnity Payment (EFT/Check)"),
        ("vendor_direct_repair", "Carrier Direct Payment to Authorized Repairer"),
        ("retained_salvage_offset", "Settled Net of Retained Equipment Salvage"),
        ("none_denied", "No Settlement (Claim Denied or Withdrawn)"),
    ]

    CLAIM_STATUS_CSS = {
        "incident_reported": "badge-slate",
        "adjuster_assigned": "badge-info",
        "proof_of_loss_filed": "badge-amber",
        "under_carrier_review": "badge-amber",
        "approved_pending_payout": "badge-info",
        "settled_paid": "badge-green",
        "denied_disputed": "badge-red",
        "closed": "badge-muted",
    }

    PERIL_TYPE_CSS = {
        "fire_lightning": "badge-red",
        "flood_water_damage": "badge-info",
        "electrical_arcing_surge": "badge-amber",
        "mechanical_breakdown": "badge-amber",
        "operator_error_accidental": "badge-slate",
        "theft_burglary": "badge-red",
        "windstorm_hail": "badge-info",
        "collision_impact": "badge-red",
        "collapse_subsidence": "badge-muted",
    }

    SETTLEMENT_METHOD_CSS = {
        "direct_indemnity_check": "badge-green",
        "vendor_direct_repair": "badge-info",
        "retained_salvage_offset": "badge-amber",
        "none_denied": "badge-red",
    }

    title = models.CharField(
        max_length=255,
        help_text="Insurance claim title or casualty incident summary",
    )
    policy = models.ForeignKey(
        "assets.AssetInsurancePolicy",
        on_delete=models.CASCADE,
        related_name="claims",
        help_text="Covering insurance policy binder",
    )
    fixed_asset = models.ForeignKey(
        "accounting.FixedAsset",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="insurance_claims",
        help_text="Financial Fixed Asset affected",
    )
    operational_asset = models.ForeignKey(
        "scm.Asset",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="insurance_claims",
        help_text="Operational equipment record",
    )
    incident_report = models.ForeignKey(
        "assets.AssetIncidentReport",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="insurance_claims",
        help_text="Linked 11.2 operational incident record",
    )
    incident_date = models.DateField(
        help_text="Date of peril occurrence or physical loss",
    )
    peril_type = models.CharField(
        max_length=32,
        choices=PERIL_TYPE_CHOICES,
        default="mechanical_breakdown",
    )
    incident_description = models.TextField(
        help_text="Detailed narrative of casualty event, damage scope, and operational interruption",
    )
    incident_location = models.CharField(
        max_length=255,
        help_text="Physical facility, plant floor, room, or geographical site of occurrence",
    )
    carrier_claim_number = models.CharField(
        max_length=100,
        blank=True,
        help_text="Insurance carrier assigned claim reference number",
    )
    adjuster_party = models.ForeignKey(
        "core.Party",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="adjusted_asset_claims",
        help_text="Independent loss adjuster or forensic engineering agency",
    )
    adjuster_name = models.CharField(
        max_length=100,
        blank=True,
        help_text="Name of designated individual adjuster",
    )
    currency = models.ForeignKey(
        "accounting.Currency",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="asset_insurance_claims",
        help_text="Claim valuation currency",
    )
    claimed_loss_amount = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal("0.00"),
        help_text="Gross estimated direct physical loss claimed",
    )
    deductible_applied = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
        help_text="Policy deductible applied against gross settlement",
    )
    salvage_recovery_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
        help_text="Proceeds recovered from scrap / residual asset sale",
    )
    settlement_payout_amount = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal("0.00"),
        help_text="Actual net cash compensation paid by carrier",
    )
    claim_status = models.CharField(
        max_length=28,
        choices=CLAIM_STATUS_CHOICES,
        default="incident_reported",
    )
    settlement_method = models.CharField(
        max_length=32,
        choices=SETTLEMENT_METHOD_CHOICES,
        default="direct_indemnity_check",
    )
    date_reported_to_carrier = models.DateField(
        null=True,
        blank=True,
        help_text="Date insurer formally notified",
    )
    proof_of_loss_date = models.DateField(
        null=True,
        blank=True,
        help_text="Date formal sworn Proof of Loss submitted",
    )
    settlement_date = models.DateField(
        null=True,
        blank=True,
        help_text="Date final payout received or release agreement executed",
    )
    settlement_notes = models.TextField(
        blank=True,
        help_text="Settlement calculation notes, subrogation details, or denial justification",
    )
    claims_officer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="managed_asset_insurance_claims",
    )
    proof_of_loss_document = models.ForeignKey(
        "core.Document",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="linked_insurance_claims",
        help_text="Sworn proof of loss, adjuster report, police report, or engineering forensic certificate",
    )

    class Meta:
        ordering = ["-incident_date", "-id"]
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "number"],
                name="assets_aicl_ten_num_uniq",
            ),
        ]
        indexes = [
            models.Index(fields=["tenant", "claim_status"], name="idx_aicl_ten_stat"),
            models.Index(fields=["tenant", "incident_date"], name="idx_aicl_ten_date"),
            models.Index(fields=["tenant", "policy"], name="idx_aicl_ten_pol"),
            models.Index(fields=["tenant", "fixed_asset"], name="idx_aicl_ten_fa"),
            models.Index(fields=["tenant", "peril_type"], name="idx_aicl_ten_peril"),
        ]

    def __str__(self):
        return f"{self.number} - {self.title}"

    @property
    def claim_status_css(self):
        return self.CLAIM_STATUS_CSS.get(self.claim_status, "badge-slate")

    @property
    def peril_type_css(self):
        return self.PERIL_TYPE_CSS.get(self.peril_type, "badge-slate")

    @property
    def settlement_method_css(self):
        return self.SETTLEMENT_METHOD_CSS.get(self.settlement_method, "badge-slate")
