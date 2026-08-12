"""SCM URLconf package — one sub-package per NavERP sub-module (4.1-4.19), one module per entity.

Each entity module exposes its own ``urlpatterns``; this __init__ sets ``app_name = "scm"`` once and
concatenates them, so every ``scm:<name>`` reverse and ``include("apps.scm.urls")`` resolves.

Django is first-match-wins, so ORDER IS BEHAVIOUR. Keep literal routes before ``<int:pk>`` ones
within a module, and when you ADD a route with a greedy converter check it against this whole
concatenated list, not just its own module.
"""
from .ProcurementManagement.Overview import urlpatterns as _procurement_overview
from .ProcurementManagement.PurchaseRequisitions import urlpatterns as _procurement_purchaserequisitions
from .ProcurementManagement.Rfqs import urlpatterns as _procurement_rfqs
from .ProcurementManagement.PurchaseOrders import urlpatterns as _procurement_purchaseorders
from .ProcurementManagement.GoodsReceiptNotes import urlpatterns as _procurement_goodsreceiptnotes
from .SupplierRelationshipManagement.SupplierProfiles import urlpatterns as _srm_supplierprofiles
from .SupplierRelationshipManagement.SupplierScorecards import urlpatterns as _srm_scorecards
from .SupplierRelationshipManagement.SupplierContracts import urlpatterns as _srm_contracts
from .SupplierRelationshipManagement.SupplierCatalogs import urlpatterns as _srm_catalogs
from .SupplierRelationshipManagement.SupplierRiskAssessments import urlpatterns as _srm_riskassessments
from .InventoryManagement.Items import urlpatterns as _inv_items
from .InventoryManagement.Locations import urlpatterns as _inv_locations
from .InventoryManagement.LotSerials import urlpatterns as _inv_lotserials
from .InventoryManagement.StockTransfers import urlpatterns as _inv_transfers
from .InventoryManagement.StockAdjustments import urlpatterns as _inv_adjustments
from .InventoryManagement.ReorderRules import urlpatterns as _inv_reorderrules
from .InventoryManagement.Reports import urlpatterns as _inv_reports
from .WarehouseManagement.PutawayTasks import urlpatterns as _wms_putaway
from .WarehouseManagement.PickTasks import urlpatterns as _wms_picks
from .WarehouseManagement.CycleCountTasks import urlpatterns as _wms_cyclecounts
from .WarehouseManagement.YardVisits import urlpatterns as _wms_yard
from .OrderManagement.SalesOrders import urlpatterns as _oms_salesorders
from .OrderManagement.SalesOrderAllocations import urlpatterns as _oms_allocations
from .TransportationManagement.Carriers import urlpatterns as _tms_carriers
from .TransportationManagement.Loads import urlpatterns as _tms_loads
from .TransportationManagement.Shipments import urlpatterns as _tms_shipments
from .TransportationManagement.FreightInvoices import urlpatterns as _tms_freightinvoices
from .DemandPlanning.SeasonalityProfiles import urlpatterns as _dp_seasonality
from .DemandPlanning.DemandForecasts import urlpatterns as _dp_forecasts
from .DemandPlanning.DemandSignals import urlpatterns as _dp_signals
from .DemandPlanning.ForecastAdjustments import urlpatterns as _dp_adjustments
from .DemandPlanning.Reports import urlpatterns as _dp_reports
from .Manufacturing.WorkCenters import urlpatterns as _mf_workcenters
from .Manufacturing.BillsOfMaterials import urlpatterns as _mf_boms
from .Manufacturing.WorkOrders import urlpatterns as _mf_workorders
from .Manufacturing.ProductionTimeLogs import urlpatterns as _mf_timelogs
from .Manufacturing.Reports import urlpatterns as _mf_reports
from .QualityManagement.InspectionPlans import urlpatterns as _qm_inspectionplans
from .QualityManagement.QualityInspections import urlpatterns as _qm_inspections
from .QualityManagement.QualityAudits import urlpatterns as _qm_audits
from .QualityManagement.NonConformances import urlpatterns as _qm_ncrs
from .QualityManagement.CapaActions import urlpatterns as _qm_capa
from .QualityManagement.Reports import urlpatterns as _qm_reports
from .ReturnsManagement.ReturnReasons import urlpatterns as _rma_reasons
from .ReturnsManagement.ReturnPolicies import urlpatterns as _rma_policies
from .ReturnsManagement.ReturnAuthorizations import urlpatterns as _rma_authorizations
from .ReturnsManagement.ReturnDispositions import urlpatterns as _rma_dispositions
from .ReturnsManagement.WarrantyClaims import urlpatterns as _rma_warranty
from .ReturnsManagement.Reports import urlpatterns as _rma_reports
from .SupplyChainAnalytics.KpiTargets import urlpatterns as _sca_kpitargets
from .SupplyChainAnalytics.KpiSnapshots import urlpatterns as _sca_kpisnapshots
from .SupplyChainAnalytics.SupplyChainAlerts import urlpatterns as _sca_alerts
from .SupplyChainAnalytics.Reports import urlpatterns as _sca_reports
from .ContractCompliance.TradeLicenses import urlpatterns as _cc_tradelicenses
from .ContractCompliance.ComplianceRequirements import urlpatterns as _cc_compliancerequirements
from .ContractCompliance.TradeDocuments import urlpatterns as _cc_tradedocuments
from .ContractCompliance.SustainabilityAssessments import urlpatterns as _cc_sustainability
from .ContractCompliance.Reports import urlpatterns as _cc_reports
from .AssetManagement.Assets import urlpatterns as _am_assets
from .AssetManagement.MaintenancePlans import urlpatterns as _am_maintenanceplans
from .AssetManagement.MaintenanceWorkOrders import urlpatterns as _am_maintenanceworkorders
from .AssetManagement.MeterReadings import urlpatterns as _am_meterreadings
from .AssetManagement.Reports import urlpatterns as _am_reports
from .LaborManagement.LaborStandards import urlpatterns as _lm_laborstandards
from .LaborManagement.LaborSessions import urlpatterns as _lm_laborsessions
from .LaborManagement.LaborActivities import urlpatterns as _lm_laboractivities
from .LaborManagement.LaborPlans import urlpatterns as _lm_laborplans
from .LaborManagement.Reports import urlpatterns as _lm_reports
# --- 4.15 Cold Chain Management ---
# Alias `_ccm_`. NOT `_cc_` (4.12 ContractCompliance) and NOT `_cp_` (4.16 Customer Portal) — a
# collision here would silently REBIND an earlier module's urlpatterns and drop its routes.
from .ColdChainManagement.ColdChainMonitors import urlpatterns as _ccm_monitors
from .ColdChainManagement.TemperatureReadings import urlpatterns as _ccm_readings
from .ColdChainManagement.TemperatureExcursions import urlpatterns as _ccm_excursions
from .ColdChainManagement.Reports import urlpatterns as _ccm_reports

# 4.16 Customer Portal. Alias `_cp_` — verified free against all fifteen shipped aliases, and in
# particular it is NOT `_cc_` (4.12 ContractCompliance) or `_ccm_` (4.15 ColdChainManagement).
# Rebinding either of those would silently drop another sub-module's routes with no import error.
from .CustomerPortal.PortalAccounts import urlpatterns as _cp_accounts
from .CustomerPortal.PortalOrderInquiries import urlpatterns as _cp_inquiries
from .CustomerPortal.PortalDocumentShares import urlpatterns as _cp_shares
from .CustomerPortal.PortalActivities import urlpatterns as _cp_activity
from .CustomerPortal.Reports import urlpatterns as _cp_reports
from .CustomerPortal.Portal import urlpatterns as _cp_portal


app_name = "scm"

urlpatterns = [
    *_procurement_overview,              # ProcurementManagement/Overview — "" (module landing)
    *_procurement_purchaserequisitions,  # ProcurementManagement/PurchaseRequisitions
    *_procurement_rfqs,                  # ProcurementManagement/Rfqs (incl. quotes)
    *_procurement_purchaseorders,        # ProcurementManagement/PurchaseOrders
    *_procurement_goodsreceiptnotes,     # ProcurementManagement/GoodsReceiptNotes
    *_srm_supplierprofiles,              # SupplierRelationshipManagement/SupplierProfiles
    *_srm_scorecards,                    # SupplierRelationshipManagement/SupplierScorecards
    *_srm_contracts,                     # SupplierRelationshipManagement/SupplierContracts
    *_srm_catalogs,                      # SupplierRelationshipManagement/SupplierCatalogs
    *_srm_riskassessments,               # SupplierRelationshipManagement/SupplierRiskAssessments
    *_inv_items,                         # InventoryManagement/Items (item + category + uom)
    *_inv_locations,                     # InventoryManagement/Locations
    *_inv_lotserials,                    # InventoryManagement/LotSerials
    *_inv_transfers,                     # InventoryManagement/StockTransfers
    *_inv_adjustments,                   # InventoryManagement/StockAdjustments
    *_inv_reorderrules,                  # InventoryManagement/ReorderRules
    *_inv_reports,                       # InventoryManagement/Reports (valuation/reorder/ledger/on-hand)
    *_wms_putaway,                       # WarehouseManagement/PutawayTasks
    *_wms_picks,                         # WarehouseManagement/PickTasks
    *_wms_cyclecounts,                   # WarehouseManagement/CycleCountTasks
    *_wms_yard,                          # WarehouseManagement/YardVisits
    # 4.5 uses `sales-orders/`, NOT `orders/` — that prefix is already PurchaseOrder's above and
    # Django is first-match-wins, so reusing it would permanently shadow the sales order list.
    *_oms_salesorders,                   # OrderManagement/SalesOrders
    *_oms_allocations,                   # OrderManagement/SalesOrderAllocations
    # 4.6 TMS prefixes (carriers/ loads/ shipments/ freight-invoices/) are all unique — no
    # collision with orders/ (PurchaseOrder) or sales-orders/ (SalesOrder) above.
    *_tms_carriers,                      # TransportationManagement/Carriers
    *_tms_loads,                         # TransportationManagement/Loads
    *_tms_shipments,                     # TransportationManagement/Shipments
    *_tms_freightinvoices,               # TransportationManagement/FreightInvoices
    # 4.7 prefixes (seasonality/ forecasts/ demand-signals/ forecast-adjustments/ safety-stock/
    # forecast-accuracy/) are all first-segment-unique against everything above — in particular
    # `forecasts/` does not collide with 4.1's `orders/`, 4.5's `sales-orders/` or 4.3's
    # `reorder-rules/`/`reorder-alerts/`, and `forecast-adjustments/`/`forecast-accuracy/` are
    # separate segments from `forecasts/`, so no pk route can swallow them.
    *_dp_seasonality,                    # DemandPlanning/SeasonalityProfiles
    *_dp_forecasts,                      # DemandPlanning/DemandForecasts
    *_dp_signals,                        # DemandPlanning/DemandSignals
    *_dp_adjustments,                    # DemandPlanning/ForecastAdjustments
    *_dp_reports,                        # DemandPlanning/Reports (safety stock + accuracy)
    # 4.8 prefixes (work-centers/ boms/ work-orders/ time-logs/ mrp/ production-schedule/) are all
    # first-segment-unique against everything above — `work-orders/` is a separate segment from
    # 4.1's `orders/` and 4.5's `sales-orders/`, so no pk route can swallow it, and every 4.8 verb
    # route sits under its own `<int:pk>/`.
    *_mf_workcenters,                    # Manufacturing/WorkCenters
    *_mf_boms,                           # Manufacturing/BillsOfMaterials
    *_mf_workorders,                     # Manufacturing/WorkOrders
    *_mf_timelogs,                       # Manufacturing/ProductionTimeLogs
    *_mf_reports,                        # Manufacturing/Reports (MRP + production schedule)
    # 4.9 prefixes (inspection-plans/ inspections/ quality-audits/ nonconformances/ capa/ coa/)
    # are all first-segment-unique against everything above — checked against the full list, not
    # just this block. In particular `inspections/` is a separate segment from 4.1's `receipts/`
    # and from 4.9's own `inspection-plans/`, `capa/` from 4.2's `catalogs/` and 4.1's
    # `categories/`, and `quality-audits/` avoids the bare `audits/` a Module-0 audit-log page
    # would want. Every 4.9 verb route sits under its own `<int:pk>/`, so none can be swallowed.
    *_qm_inspectionplans,                # QualityManagement/InspectionPlans (criteria master)
    *_qm_inspections,                    # QualityManagement/QualityInspections
    *_qm_audits,                         # QualityManagement/QualityAudits
    *_qm_ncrs,                           # QualityManagement/NonConformances
    *_qm_capa,                           # QualityManagement/CapaActions
    *_qm_reports,                        # QualityManagement/Reports (Certificate of Analysis)
    # ---------------------------------------------------------------------------------------
    # 4.10 COLLISION CHECK — nine new first segments, each checked against the WHOLE list above
    # and not merely against this block:
    #
    #   returns/              vs 4.1 `orders/`, 4.5 `sales-orders/`, 4.8 `work-orders/`,
    #                            4.3 `reorder-rules/`/`reorder-alerts/`, 4.1 `receipts/`
    #                            — all separate first segments; `returns/` is free.
    #   return-reasons/       ) four distinct segments, none a prefix of another as far as Django
    #   return-policies/      ) is concerned (it matches whole path components, so
    #   return-dispositions/  ) `return-tracking/` cannot be captured by `returns/<int:pk>/`).
    #   return-tracking/      )
    #   returns-bench/        — distinct from `returns/`: `returns-bench` is ONE component and is
    #                           never split at the hyphen.
    #   refund-queue/ · return-portal/ · warranty-claims/ — no prior segment starts with
    #                           refund, portal or warranty anywhere in the app.
    #
    # `return-tracking/<str:token>/` is the module's only greedy converter and it sits ALONE on
    # its own first segment, so it can neither shadow nor be shadowed by any pk route. Within each
    # block below, literal routes (`add/`) precede the `<int:pk>/` ones.
    *_rma_reasons,                       # ReturnsManagement/ReturnReasons (master, no bullet)
    *_rma_policies,                      # ReturnsManagement/ReturnPolicies (master, no bullet)
    *_rma_authorizations,                # ReturnsManagement/ReturnAuthorizations (the RMA)
    *_rma_dispositions,                  # ReturnsManagement/ReturnDispositions (the bench)
    *_rma_warranty,                      # ReturnsManagement/WarrantyClaims
    *_rma_reports,                       # ReturnsManagement/Reports (queues + portal + public)
    # ---------------------------------------------------------------------------------------
    # 4.11 COLLISION CHECK — eight new first segments, each checked against the WHOLE list above
    # and not merely against this block:
    #
    #   kpi-targets/ · kpi-snapshots/  — nothing anywhere in the app starts with `kpi`. Both are
    #                           distinct whole components, so neither can swallow the other.
    #   alerts/               — 4.3 owns `reorder-alerts/`. Django matches WHOLE path components
    #                           and never splits at a hyphen, so `alerts` and `reorder-alerts` are
    #                           unrelated segments and neither shadows the other. Do NOT "tidy"
    #                           either one to match the other.
    #   disruption-risk/      — 4.2 owns `risk-assessments/`. Again a distinct first component;
    #                           `disruption-risk` is one component, not `disruption` + `risk`.
    #   inventory-analytics/ · spend-analytics/ · logistics-kpis/ · margin-analytics/
    #                         — nothing existing starts with inventory, spend, logistics or margin.
    #
    # The CSV exports are literal `export/` sub-routes under segments already claimed above, so
    # they add ZERO new first segments and zero new collision surface.
    #
    # 4.11 introduces NO greedy `<str:…>` converter — 4.10's `return-tracking/<str:token>/` remains
    # the module's only one, and it sits alone on its own first segment. Within each module below,
    # literal routes (`add/`, `export/`, `capture/`, `detect/`) precede every `<int:pk>/` one.
    *_sca_kpitargets,                    # SupplyChainAnalytics/KpiTargets (the target master)
    *_sca_kpisnapshots,                  # SupplyChainAnalytics/KpiSnapshots (frozen history)
    *_sca_alerts,                        # SupplyChainAnalytics/SupplyChainAlerts (the inbox)
    *_sca_reports,                       # SupplyChainAnalytics/Reports (the five bullet pages)

    # 4.12 COLLISION CHECK — every first segment 4.12 adds, checked against the whole concatenated
    # urlconf above rather than against its own module:
    #   compliance-requirements/ · compliance-checks/ — nothing anywhere in scm starts with
    #                         `compliance`. Django matches WHOLE path components and never splits at
    #                         a hyphen, so these two cannot shadow each other either.
    #   trade-documents/ · trade-licenses/ — nothing anywhere starts with `trade`.
    #   sustainability-assessments/ — nothing starts with `sustainability`. Note 4.2 owns
    #                         `risk-assessments/`: an unrelated FIRST segment, not a `…/assessments`
    #                         suffix, so there is no overlap to reason about.
    #   carbon-footprint/ — nothing starts with `carbon`; `carbon-footprint/export/` is a literal
    #                         sub-route of that same segment, so the report pair adds ZERO new
    #                         first segments beyond the one.
    #
    # 4.12 adds NO new first segment `contracts/` — 4.2 already owns it, and the Contract Repository
    # sidebar bullet points at 4.2's list rather than a second contract table.
    #
    # 4.12 introduces NO greedy `<str:…>` converter; 4.10's `return-tracking/<str:token>/` remains
    # the module's only one and sits alone on its own first segment. Within each module below,
    # literal routes (`add/`, `export/`, `print/`) precede every `<int:pk>/` one.
    *_cc_tradelicenses,                  # ContractCompliance/TradeLicenses (register + balance)
    *_cc_compliancerequirements,         # ContractCompliance/ComplianceRequirements (+ checks)
    *_cc_tradedocuments,                 # ContractCompliance/TradeDocuments (BoL / CI / packing)
    *_cc_sustainability,                 # ContractCompliance/SustainabilityAssessments (ESG)
    *_cc_reports,                        # ContractCompliance/Reports (carbon footprint estimate)

    # ---------------------------------------------------------------------------------------
    # 4.13 COLLISION CHECK — nine new first segments, every one re-verified against the WHOLE
    # concatenated urlconf above rather than against its own block:
    #
    #   assets/ · asset-spare-parts/ · asset-depreciation/
    #                         — NOTHING anywhere in scm starts with `asset`. Django matches WHOLE
    #                           path components and never splits one at a hyphen, so these are three
    #                           unrelated segments and none can shadow either of the others. Do not
    #                           "tidy" any of them to look like another.
    #   maintenance-plans/ · maintenance-work-orders/ · maintenance-work-order-tasks/
    #                         — nothing anywhere starts with `maintenance`; again three distinct
    #                           whole components, so the pk routes in one cannot capture another.
    #
    #                           **`maintenance-work-orders/` is a DISTINCT whole path component from
    #                           4.8's `work-orders/` (and from 4.1's `orders/` and 4.5's
    #                           `sales-orders/`).** Django never splits a component at the hyphen, so
    #                           neither can shadow the other — and neither may ever be "tidied" to
    #                           look like the other, because they are different documents:
    #                           4.8's WorkOrder MAKES product and consumes components against a BOM;
    #                           4.13's MaintenanceWorkOrder REPAIRS a machine and consumes spares
    #                           against an asset. `scm:workorder_list` and
    #                           `scm:maintenanceworkorder_list` are two live, unrelated pages.
    #   meter-readings/       — nothing anywhere starts with `meter`.
    #   pm-forecast/          — nothing anywhere starts with `pm`.
    #   spare-parts/          — nothing anywhere starts with `spare`; a separate component from
    #                           4.13's own `asset-spare-parts/`, and a different thing (the report is
    #                           4.3's item ledger filtered; the child is one machine's parts list).
    #
    # 4.13 introduces NO greedy `<str:…>` converter — 4.10's `return-tracking/<str:token>/` remains
    # the app's only one and sits alone on its own first segment. Within each module below, literal
    # routes (`add/`) precede every `<int:pk>/` one, or the create page is swallowed and 404s as
    # "asset 'add' not found". Every verb route sits under its own `<int:pk>/` and is POST-only at
    # the view, so a GET to one is a 405 rather than a silent state change.
    #
    # 4.13 adds no `fixed-assets/` segment: Asset Depreciation is a COMPUTED report that READS
    # accounting.FixedAsset, and there is no `spare-parts/<int:pk>/` CRUD either — the storeroom page
    # is 4.3's Item/StockMove/ReorderRule, filtered.
    *_am_assets,                         # AssetManagement/Assets (register + the parts-list child)
    *_am_maintenanceplans,               # AssetManagement/MaintenancePlans (PM programme + generate)
    *_am_maintenanceworkorders,          # AssetManagement/MaintenanceWorkOrders (ladder + issue)
    *_am_meterreadings,                  # AssetManagement/MeterReadings (append-only — no edit/delete)
    *_am_reports,                        # AssetManagement/Reports (PM board + MRO + repair-vs-replace)

    # --- 4.14 Labor Management -----------------------------------------------------------------
    # Eight new first segments, every one free: nothing anywhere in `scm` starts with `labor`.
    # Django matches WHOLE path components and never splits one at a hyphen, so `labor-standards`,
    # `labor-sessions`, `labor-activities`, `labor-plans`, `labor-plan-lines`, `labor-board`,
    # `labor-payroll-export` and `labor-scorecard` are eight unrelated components and none can
    # shadow another — and none may ever be "tidied" into looking like another.
    #
    # Near neighbours that are NOT collisions, checked rather than assumed:
    #   loads/          — 4.6's transport loads. Shares no whole component with `labor-*`.
    #   locations/      — 4.3's bin master.
    #   lot-serials/    — 4.3's lot/serial master.
    #   production-time-logs/ — 4.8's shop-floor interval. `scm:productiontimelog_list` and
    #                     `scm:laboractivity_list` are two live, unrelated pages: one books time at a
    #                     WORK CENTRE against a work order, the other books it in a WAREHOUSE SHIFT
    #                     against a pick/putaway/count task. Neither is the other's rename.
    #
    # 4.14 introduces NO greedy `<str:…>` converter — 4.10's `return-tracking/<str:token>/` remains
    # the app's only one. Within each module below, literal routes (`add/`, `clock-in/`, `assign/`,
    # `export/`) precede every `<int:pk>/` one, or the create page is swallowed and 404s as
    # "labor standard 'add' not found". Every verb sits under its own route and is POST-only at the
    # view, so a GET to one is a 405 rather than a silent state change.
    #
    # 4.14 adds NO route under `pick-tasks/`, `putaway-tasks/` or `cycle-counts/`. The assignment
    # board's bulk verbs live on `labor-board/assign/` and `labor-board/unassign/` and write 4.4's
    # EXISTING `assigned_to` column, so 4.4's urlconf and its three tables are untouched.
    *_lm_laborstandards,                 # LaborManagement/LaborStandards (library + activate/archive)
    *_lm_laborsessions,                  # LaborManagement/LaborSessions (the shift + its verb ladder)
    *_lm_laboractivities,                # LaborManagement/LaborActivities (booked intervals)
    *_lm_laborplans,                     # LaborManagement/LaborPlans (plan + generate + the line)
    *_lm_reports,                        # LaborManagement/Reports (board + payroll export + scorecard)

    # --- 4.15 Cold Chain Management ------------------------------------------------------------
    # SIX new first segments, every one free — checked against this WHOLE concatenated list, not
    # merely against the 4.15 block: nothing anywhere in `scm` starts with `cold`, `temperature` or
    # `reefer`. Django matches WHOLE path components and never splits one at a hyphen, so
    # `cold-chain-monitors`, `cold-storage-report`, `cold-chain-compliance`, `temperature-readings`,
    # `temperature-excursions` and `reefer-board` are six unrelated components; none can shadow
    # another, and none may ever be "tidied" to look like another.
    #
    # Near neighbours that are NOT collisions, checked rather than assumed:
    #   compliance-requirements/ · compliance-checks/ — 4.12's. A different whole component from
    #                     `cold-chain-compliance`, and a different thing: 4.12 tracks trade licences
    #                     and ESG obligations, 4.15 reports the temperature record.
    #   categories/ · locations/ · lot-serials/ — 4.3's masters, all read BY the cold-storage page
    #                     and none of them touched by it.
    #   labor-board/    — 4.14's computed board. `reefer-board/` is the other one; two live,
    #                     unrelated pages.
    #   carriers/ · shipments/ — 4.6's. A shipment can BE a monitor's subject; it takes no new route.
    #
    # 4.15 introduces NO greedy `<str:…>` converter — 4.10's `return-tracking/<str:token>/` remains
    # the app's only one. Within each module below, literal routes (`add/`, `detect/`) precede every
    # `<int:pk>/` one. Every verb sits under its own route and is POST-only at the view, so a GET to
    # one is a 405 rather than a silent state change.
    #
    # 4.15 adds NO route under `assets/`, `maintenance-plans/` or `maintenance-work-orders/`: the
    # reefer board lives entirely on `reefer-board/` and 4.13's urlconf is untouched. The two nested
    # reading routes (`cold-chain-monitors/<int:pk>/readings/add|import/`) are declared in the
    # READINGS module beside the thing they create; they carry more segments than
    # `cold-chain-monitors/<int:pk>/`, so their position after it here cannot shadow them.
    *_ccm_monitors,                      # ColdChainManagement/ColdChainMonitors (register + detect)
    *_ccm_readings,                      # ColdChainManagement/TemperatureReadings (append-only)
    *_ccm_excursions,                    # ColdChainManagement/TemperatureExcursions (queue + ladder)
    *_ccm_reports,                       # ColdChainManagement/Reports (cold storage + compliance + reefers)

    # --- 4.16 Customer Portal ---
    # EIGHT unrelated first segments: `portal-accounts`, `portal-inquiries`,
    # `portal-document-shares`, `portal-activity`, `portal-order-tracking`,
    # `portal-catalog-preview`, `portal` and `portal-documents`. Django matches WHOLE path
    # components and never splits one at a hyphen, so none of these shadows another and none may
    # ever be "tidied" into another's shape. The only pre-existing `portal` paths in this app are
    # 4.10's `return-portal/` and `return-portal/request/` — a different first segment entirely.
    # `crm`'s own `portal/` and `portal-access/` routes live in a different app mounted at `/crm/`
    # and cannot collide.
    #
    # VIEW-NAME check (the `scm:` namespace is flat): 4.10 already owns `return_portal` and
    # `portal_return_create`; 4.16 reuses neither.
    #
    # `portal-documents/<str:token>/` is only the SECOND greedy `<str:…>` converter in the whole app
    # (4.10's `return-tracking/<str:token>/` was the first). It sits alone on its own first segment,
    # so it cannot swallow a neighbour — the next greedy converter added WITHOUT this check is the
    # one that breaks something.
    *_cp_accounts,                       # CustomerPortal/PortalAccounts (the enablement console)
    *_cp_inquiries,                      # CustomerPortal/PortalOrderInquiries (triage over crm.Case)
    *_cp_shares,                         # CustomerPortal/PortalDocumentShares (+ admin-gated revoke)
    *_cp_activity,                       # CustomerPortal/PortalActivities (append-only, list+detail)
    *_cp_reports,                        # CustomerPortal/Reports (order tracking + catalog preview)
    *_cp_portal,                         # CustomerPortal/Portal (gated customer surface + token download)
]
