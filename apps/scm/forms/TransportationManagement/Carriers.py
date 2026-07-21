"""SCM 4.6 Transportation Management System — Carrier form + rate-card formset."""
from apps.scm.forms._common import *  # noqa: F401,F403
from apps.scm.forms._common import _active_currencies, _carrier_parties, _scope_to_parent
from apps.scm.models import Carrier, CarrierRateCard


class CarrierForm(TenantModelForm):
    """The carrier master.

    EXCLUDES `number` (auto) and the derived scorecard fields (`on_time_delivery_pct`,
    `performance_summary`) — those are recomputed from delivered-shipment history, never typed.
    `party` is narrowed to supplier/vendor/partner parties: a carrier is procured from, so it reuses
    the spine rather than a standalone name/address table (the 4.2 SupplierProfile pattern).
    """

    class Meta:
        model = Carrier
        fields = ["party", "carrier_type", "primary_mode", "service_level", "scac_code",
                  "mc_number", "dot_number", "insurance_certificate_expiry", "primary_contact_name",
                  "primary_contact_email", "primary_contact_phone", "is_preferred", "status", "notes"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Party has no carrier-only flag, so TenantModelForm's generic scoping would offer every
        # party. Narrow it to the roles a carrier can hold.
        self.fields["party"].queryset = _carrier_parties(self.tenant)


class CarrierRateCardForm(TenantModelForm):
    """One lane/mode rate. `currency` is GLOBAL (no tenant FK) so it needs the shared scoping helper;
    the parent `carrier` FK is set by the formset, never chosen on the line."""

    class Meta:
        model = CarrierRateCard
        fields = ["lane_name", "origin_region", "destination_region", "mode", "equipment_type",
                  "rate_basis", "base_rate", "fuel_surcharge_pct", "min_charge", "transit_days",
                  "currency", "effective_from", "effective_to", "is_active"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _active_currencies(self)


CarrierRateCardFormSet = inlineformset_factory(
    Carrier, CarrierRateCard, form=CarrierRateCardForm, extra=1, can_delete=True,
)
